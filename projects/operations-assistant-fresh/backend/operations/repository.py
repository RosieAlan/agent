import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import text

from db import engine
from .service import build_report, next_daily_run

INVENTORY_SQL = '''SELECT s.code store_code,s.name store_name,p.sku,p.name product_name,
 i.available,i.reserved,i.inbound FROM ops_inventory i
 JOIN ops_products p ON p.id=i.product_id JOIN ops_stores s ON s.id=i.store_id'''


def execute(conn, sql, params=None):
    return conn.execute(text(sql), params or {})


def db_now(conn):
    return execute(conn, 'SELECT UTC_TIMESTAMP(6)').scalar_one()


def notify_failed(conn):
    # 失败状态与收件箱通知同事务落库，run_id唯一约束保证恢复后重复扫描安全。
    execute(conn, '''INSERT IGNORE INTO ops_automation_notifications (run_id,title,body,created_at)
      SELECT r.id,'运营任务执行失败','任务已达到重试上限，请检查服务日志后重新提交。',UTC_TIMESTAMP(6)
      FROM ops_automation_runs r WHERE r.status='failed'
      AND NOT EXISTS (SELECT 1 FROM ops_automation_notifications n WHERE n.run_id=r.id)''')


def serialize(row):
    item = dict(row)
    for key, value in item.items():
        if hasattr(value, 'isoformat'):
            item[key] = value.isoformat() + 'Z'
    if 'result' in item and isinstance(item['result'], str):
        item['result'] = json.loads(item['result'])
    for key in ('is_read', 'enabled'):
        if key in item:
            item[key] = bool(item[key])
    if 'threshold_value' in item:
        item['threshold'] = item.pop('threshold_value')
    return item


RUN_FIELDS = 'id,kind,status,created_at,started_at,finished_at,attempts,error,result'


def inventory(sku=None, limit=200, threshold=20):
    with engine.connect() as conn:
        rows = execute(conn, INVENTORY_SQL + (' WHERE p.sku=:sku' if sku else '') +
                       ' ORDER BY s.code,p.sku LIMIT :limit', {'sku': sku, 'limit': limit}).mappings()
        return build_report([dict(row) for row in rows], threshold, db_now(conn))['items']


def get_run(run_id):
    with engine.connect() as conn:
        row = execute(conn, f'SELECT {RUN_FIELDS} FROM ops_automation_runs WHERE id=:id',
                      {'id': run_id}).mappings().first()
        return serialize(row) if row else None


def enqueue(conn, kind, threshold, key, now):
    run_id = str(uuid4())
    execute(conn, '''INSERT INTO ops_automation_runs
      (id,kind,idempotency_key,threshold_value,created_at,available_at)
      VALUES (:id,:kind,:key,:threshold,:now,:now)
      ON DUPLICATE KEY UPDATE id=id''',
      {'id': run_id, 'kind': kind, 'key': key, 'threshold': threshold, 'now': now})
    row = execute(conn, f'SELECT {RUN_FIELDS},threshold_value FROM ops_automation_runs WHERE idempotency_key=:key',
                  {'key': key}).mappings().one()
    if row['kind'] != kind or row['threshold_value'] != threshold:
        raise ValueError('idempotency_conflict')
    result = serialize(row)
    result.pop('threshold')
    return result


def create_run(kind, threshold, key):
    with engine.begin() as conn:
        return enqueue(conn, kind, threshold, key, db_now(conn))


def list_rows(table, fields='*', limit=100):
    # 表名均由本模块常量调用，用户参数通过绑定传入。
    with engine.connect() as conn:
        return [serialize(row) for row in execute(conn,
                f'SELECT {fields} FROM {table} ORDER BY ' +
                ('created_at DESC,id DESC' if table.endswith(('runs', 'notifications')) else
                 'kind' if table.endswith('schedules') else 'updated_at DESC,id DESC') +
                ' LIMIT :limit', {'limit': limit}).mappings()]


def patch_item(table, item_id, field, value):
    with engine.begin() as conn:
        execute(conn, f'UPDATE {table} SET {field}=:value' +
                (',updated_at=UTC_TIMESTAMP(6)' if table.endswith('todos') else '') +
                ' WHERE id=:id', {'id': item_id, 'value': value})
        row = execute(conn, f'SELECT * FROM {table} WHERE id=:id', {'id': item_id}).mappings().first()
        return serialize(row) if row else None


def save_schedule(kind, enabled, daily_time, threshold):
    with engine.begin() as conn:
        # 与调度器锁同一行，保存配置与推进到期时间串行执行。
        execute(conn, 'SELECT kind FROM ops_automation_schedules WHERE kind=:kind FOR UPDATE', {'kind': kind})
        execute(conn, '''UPDATE ops_automation_schedules SET enabled=:enabled,daily_time=:time,
          threshold_value=:threshold,next_run_at=:next WHERE kind=:kind''',
          {'kind': kind, 'enabled': enabled, 'time': daily_time, 'threshold': threshold,
           'next': next_daily_run(daily_time, db_now(conn)) if enabled else None})
        return serialize(execute(conn, 'SELECT * FROM ops_automation_schedules WHERE kind=:kind',
                                 {'kind': kind}).mappings().one())


def overview():
    with engine.connect() as conn:
        low = execute(conn, 'SELECT COUNT(*) FROM ops_inventory WHERE available<20').scalar_one()
        todos = execute(conn, "SELECT COUNT(*) FROM ops_automation_todos WHERE status='open'").scalar_one()
        unread = execute(conn, 'SELECT COUNT(*) FROM ops_automation_notifications WHERE is_read=FALSE').scalar_one()
        seen = execute(conn, 'SELECT MAX(last_seen) FROM ops_automation_workers').scalar_one()
        now = db_now(conn)
        row = execute(conn, f'SELECT {RUN_FIELDS} FROM ops_automation_runs ORDER BY created_at DESC,id DESC LIMIT 1').mappings().first()
        return {'data_source': 'synthetic_demo', 'counts': {'low_stock': low, 'open_todos': todos,
                'unread_notifications': unread}, 'worker': {'healthy': bool(seen and now-seen < timedelta(seconds=30)),
                'last_seen': seen.isoformat()+'Z' if seen else None}, 'latest_run': serialize(row) if row else None}


def claim(worker_id):
    with engine.begin() as conn:
        now = db_now(conn)
        execute(conn, '''INSERT INTO ops_automation_workers (id,last_seen) VALUES (:id,:now)
          ON DUPLICATE KEY UPDATE last_seen=:now''', {'id': worker_id, 'now': now})
        # 到期计划逐行加锁，幂等键按计划时间生成，保障多进程调度安全。
        due = execute(conn, '''SELECT * FROM ops_automation_schedules WHERE enabled=TRUE
          AND next_run_at<=:now ORDER BY kind FOR UPDATE SKIP LOCKED''', {'now': now}).mappings().all()
        for schedule in due:
            enqueue(conn, schedule['kind'], schedule['threshold_value'],
                    f"schedule:{schedule['kind']}:{schedule['next_run_at'].isoformat()}", now)
            execute(conn, 'UPDATE ops_automation_schedules SET next_run_at=:next WHERE kind=:kind',
                    {'next': next_daily_run(schedule['daily_time'], now), 'kind': schedule['kind']})
        execute(conn, '''UPDATE ops_automation_runs SET status=IF(attempts>=3,'failed','queued'),
          error='worker_lease_expired',worker_id=NULL,lease_until=NULL,available_at=:now,
          finished_at=IF(attempts>=3,:now,NULL)
          WHERE status='running' AND lease_until<:now''', {'now': now})
        notify_failed(conn)
        row = execute(conn, '''SELECT * FROM ops_automation_runs WHERE status='queued'
          AND available_at<=:now AND attempts<3 ORDER BY created_at,id LIMIT 1
          FOR UPDATE SKIP LOCKED''', {'now': now}).mappings().first()
        if row is None:
            return None
        execute(conn, '''UPDATE ops_automation_runs SET status='running',attempts=attempts+1,
          started_at=COALESCE(started_at,:now),error=NULL,worker_id=:worker,
          lease_until=:lease WHERE id=:id''',
          {'id': row['id'], 'worker': worker_id, 'now': now, 'lease': now+timedelta(seconds=60)})
        return dict(row)


def complete(run_id, worker_id):
    # 所有业务副作用与完成标记共用事务；锁持有期间由数据库负责互斥。
    with engine.begin() as conn:
        run = execute(conn, 'SELECT * FROM ops_automation_runs WHERE id=:id FOR UPDATE',
                      {'id': run_id}).mappings().one()
        now = db_now(conn)
        if run['status'] != 'running' or run['worker_id'] != worker_id or run['lease_until'] < now:
            return False
        items = [dict(row) for row in execute(conn, INVENTORY_SQL+' ORDER BY s.code,p.sku').mappings()]
        report = build_report(items, run['threshold_value'], now)
        for item in report['items']:
            if item['is_low_stock']:
                execute(conn, '''INSERT INTO ops_automation_todos
                  (store_code,sku,title,status,available,threshold_value,updated_at)
                  VALUES (:store_code,:sku,:title,'open',:available,:threshold,:now)
                  ON DUPLICATE KEY UPDATE title=:title,status='open',available=:available,
                  threshold_value=:threshold,updated_at=:now''',
                  {**item, 'title': f"{item['store_code']} / {item['sku']} 库存补货", 'threshold': run['threshold_value'], 'now': now})
            else:
                execute(conn, '''UPDATE ops_automation_todos SET status='done',available=:available,
                  threshold_value=:threshold,updated_at=:now WHERE store_code=:store_code AND sku=:sku''',
                  {**item, 'threshold': run['threshold_value'], 'now': now})
        execute(conn, '''INSERT INTO ops_automation_notifications (run_id,title,body,created_at)
          VALUES (:id,:title,:body,:now)''', {'id': run_id,
          'title': '运营日报已生成' if run['kind']=='daily_report' else '库存巡检已完成',
          'body': report['summary'], 'now': now})
        execute(conn, '''UPDATE ops_automation_runs SET status='completed',finished_at=:now,
          result=:result,error=NULL,lease_until=NULL,worker_id=NULL WHERE id=:id''',
          {'id': run_id, 'result': json.dumps(report, ensure_ascii=False), 'now': now})
        return True


def fail(run_id, worker_id):
    with engine.begin() as conn:
        now = db_now(conn)
        execute(conn, '''UPDATE ops_automation_runs SET status=IF(attempts>=3,'failed','queued'),
          error='execution_failed',finished_at=IF(attempts>=3,:now,NULL),
          available_at=:retry,worker_id=NULL,lease_until=NULL
          WHERE id=:id AND status='running' AND worker_id=:worker''',
          {'id': run_id, 'worker': worker_id, 'now': now, 'retry': now+timedelta(seconds=10)})
        notify_failed(conn)
