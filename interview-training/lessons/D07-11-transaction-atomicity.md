# D07：事务——库存修改与修改日志一起提交

日期2026-11-02；实际D07，日历D12。原第五章数据库基础与岗位事务/审计补充，生产审计后续D26展开。

必备：同一个事务中的数据库写入一起提交或一起回滚。熟练：BEGIN开始、COMMIT提交、ROLLBACK撤销本事务修改；SQLAlchemy engine.begin正常退出提交、异常退出回滚。熟悉：数据库事务覆盖数据库写入，外部HTTP/模型/通知副作用需另设计outbox、重试与幂等（后续单元）。事务原子性与version并发冲突检查分别负责多步完整和过期写入控制。

调用：当前PATCH→main→update_inventory_in_db→engine.begin→条件UPDATE→提交→返回；库存审计写入尚未接入。此块用两张独立临时表演示两条写入，正式接口不修改。

## DBeaver练习

连接agent_training，在同一SQL编辑器执行以下各组，确认自动提交模式；事务组从BEGIN到COMMIT/ROLLBACK整体执行。关闭对应数据库会话会删除临时表；练习完也可显式DROP清理。

```sql
-- 本窗口专用的两张临时表，关闭数据库会话后自动清理。
CREATE TEMP TABLE lesson_stock (
    sku TEXT PRIMARY KEY,
    stock INTEGER NOT NULL CHECK (stock >= 0)
);
CREATE TEMP TABLE lesson_stock_log (
    sku TEXT NOT NULL,
    new_stock INTEGER NOT NULL,
    operator_id TEXT NOT NULL
);
INSERT INTO lesson_stock VALUES ('SKU-TEST-001', 25);

-- 第一组：两条写入一起提交。
BEGIN;
UPDATE lesson_stock SET stock = 20 WHERE sku = 'SKU-TEST-001';
INSERT INTO lesson_stock_log VALUES ('SKU-TEST-001', 20, 'user-001');
COMMIT;

-- 第二组：模拟操作取消，撤销本组两条写入。
BEGIN;
UPDATE lesson_stock SET stock = 5 WHERE sku = 'SKU-TEST-001';
INSERT INTO lesson_stock_log VALUES ('SKU-TEST-001', 5, 'user-001');
ROLLBACK;

-- 查看最终库存与已提交的修改日志。
SELECT * FROM lesson_stock;
SELECT * FROM lesson_stock_log;

```

预期库存20，日志仅一行20/user-001。ROLLBACK只撤销第二组，保留第一组已提交结果。观察后执行DROP TABLE lesson_stock_log; DROP TABLE lesson_stock;清理。

Python对应：同一个with engine.begin() as connection内连续两次connection.execute，SQL和参数使用本实验表；成功退出提交，异常传出时自动回滚，最后归还连接。except放在事务with外侧；数据库写入错误应传播至HTTP层映射响应。正式增加审计表时需Alembic迁移、权限过滤、版本比较和事务内日志写入；当前仅教学实验，尚未接入正式业务。

面试答案：事务将一组数据库操作组织成整体。库存更新和审计记录应放在同一事务中，全部成功后提交，任一步失败则回滚。数据库事务保护数据库修改，外部平台操作通过任务状态、幂等与补偿等机制协调。当前默认隔离级别与并发读取下一块继续。

教师真实PG验证：成功组保留20/1条日志，主动回滚组仍20/1；额外以日志operator_id=NULL触发NOT NULL错误，异常回滚后仍20/1。临时表已删除，连接占用0，业务库存未改，模型调用0。学生提交连接池实际六行输出通过；本块学生事务输出待收，独立完整通过1/32。

参考：https://www.postgresql.org/docs/16/tutorial-transactions.html

