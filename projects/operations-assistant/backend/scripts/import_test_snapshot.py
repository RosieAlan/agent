"""Copy selected authorized test data into an empty project database.

Run from backend: python scripts/import_test_snapshot.py
The source transaction is read-only. A populated target is preserved.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import URL, MetaData, Table, create_engine, select, func, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.target import local_project_url

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

QUERIES = {
    "stores": "SELECT sid AS id, name, account_name AS account_code, country, status FROM lx_seller_info",
    "products": "SELECT id AS source_id, sku, product_name AS name, brand_name AS brand, category_name AS category, update_time AS source_updated_at FROM lx_product",
    "inventory_snapshots": "SELECT id AS source_id, sid AS store_id, account, m_sku AS msku, sku, asin, afn_fulfillable_quantity AS available, reserved_customerorders AS reserved, afn_inbound_shipped_quantity AS inbound, update_time AS source_updated_at FROM lx_fba_inventory",
}


def main():
    target_url = local_project_url(os.environ["MIGRATION_DATABASE_URL"])
    source = create_engine(URL.create("mysql+pymysql", username=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"], host=os.environ["MYSQL_HOST"], port=int(os.environ["MYSQL_PORT"]), database=os.environ["MYSQL_DATABASE"], query={"charset": "utf8mb4"}), connect_args={"connect_timeout": 5, "read_timeout": 30})
    target = create_engine(target_url)
    imported_at = datetime.now(timezone.utc)
    counts = {}
    try:
        # 目标库单事务：三张表和导入记录一起成功，失败一起回滚。
        with target.begin() as destination, source.connect() as origin:
            # 锁住本项目的导入任务，防止两个导入进程同时写入。
            destination.execute(text("SELECT pg_advisory_xact_lock(68130701)"))
            tables = {name: Table(name, MetaData(), autoload_with=destination) for name in [*QUERIES, "data_imports"]}
            if any(destination.scalar(select(func.count()).select_from(table)) for table in tables.values()):
                raise RuntimeError("目标已有数据，本次导入停止；现有数据保持原样")
            origin.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            origin.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            for name, query in QUERIES.items():
                rows = [dict(row) for row in origin.execute(text(query)).mappings()]
                for row in rows:
                    for field in ["id", "source_id", "store_id"]:
                        if field in row and row[field] is not None:
                            row[field] = str(row[field])
                    row["imported_at"] = imported_at
                for start in range(0, len(rows), 500):
                    destination.execute(tables[name].insert(), rows[start:start + 500])
                copied = destination.scalar(select(func.count()).select_from(tables[name]))
                if copied != len(rows):
                    raise RuntimeError("导入数量核对失败")
                counts[name] = copied
            counts["unmapped_inventory"] = destination.scalar(text("SELECT count(*) FROM inventory_snapshots i LEFT JOIN stores s ON i.store_id = s.id WHERE s.id IS NULL"))
            destination.execute(tables["data_imports"].insert().values(id=str(uuid4()), source="authorized_test_snapshot", imported_at=imported_at, counts=counts))
        print(json.dumps({"status": "imported", "imported_at": imported_at.isoformat(), "counts": counts}))
    finally:
        source.dispose()
        target.dispose()


if __name__ == "__main__":
    main()
