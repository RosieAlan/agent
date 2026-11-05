from sqlalchemy import bindparam, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import AccessDenied, DependencyUnavailable
from app.db.session import get_engine

STORES = text("""
    SELECT id, name, account_code, country
    FROM stores
    WHERE account_code IN :account_codes AND status = 1
    ORDER BY id
""").bindparams(bindparam("account_codes", expanding=True))

STORE = text("""
    SELECT id, name FROM stores
    WHERE id = :store_id AND account_code IN :account_codes AND status = 1
""").bindparams(bindparam("account_codes", expanding=True))

INVENTORY = text("""
    SELECT account, msku, sku, asin, available, reserved, inbound,
           source_updated_at, imported_at
    FROM inventory_snapshots
    WHERE account = :account AND msku = :msku AND store_id = :store_id
    LIMIT 1
""")


def list_stores(account_codes: list[str]) -> list[dict]:
    if not account_codes:
        return []
    try:
        with get_engine().connect() as connection:
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            return [dict(row) for row in connection.execute(STORES, {"account_codes": account_codes}).mappings()]
    except SQLAlchemyError as error:
        raise DependencyUnavailable("店铺数据库暂时不可用") from error


def get_inventory(store_id: str, msku: str, account_codes: list[str]) -> dict | None:
    if not account_codes:
        raise AccessDenied()
    try:
        with get_engine().connect() as connection:
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            # 先查目标店铺是否属于当前用户的公司账号授权范围。
            store = connection.execute(STORE, {"store_id": store_id, "account_codes": account_codes}).mappings().first()
            if store is None:
                raise AccessDenied()
            # 库存继续绑定已授权店铺的账号和sid，防止相同商品跨店铺串查。
            row = connection.execute(INVENTORY, {"account": store["name"], "store_id": store["id"], "msku": msku}).mappings().first()
            return dict(row) if row else None
    except SQLAlchemyError as error:
        raise DependencyUnavailable("库存数据库暂时不可用") from error
