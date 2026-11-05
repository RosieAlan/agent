"""Add synthetic inventory for the Agent tool lesson."""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = "0002_demo_inventory"
down_revision = "0001_business_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    demo = op.create_table("demo_inventory",
        sa.Column("source_id", sa.String(64), primary_key=True),
        sa.Column("store_id", sa.String(64), nullable=False),
        sa.Column("account", sa.String(255), nullable=False),
        sa.Column("msku", sa.String(128), nullable=False),
        sa.Column("sku", sa.String(255), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("available", sa.BigInteger(), nullable=False),
        sa.Column("reserved", sa.BigInteger(), nullable=False),
        sa.Column("inbound", sa.BigInteger(), nullable=False),
        sa.Column("imported_at", DATETIME(fsp=6), nullable=False),
        sa.UniqueConstraint("store_id", "msku", name="uq_demo_store_msku"),
        mysql_engine="InnoDB")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(demo, [
        {"source_id": "demo-1", "store_id": "DEMO-STORE-001", "account": "演示店铺", "msku": "DEMO-EARBUDS-01", "sku": "DEMO-PRODUCT-01", "product_name": "无线耳机（模拟商品）", "available": 28, "reserved": 8, "inbound": 120, "imported_at": now},
        {"source_id": "demo-2", "store_id": "DEMO-STORE-001", "account": "演示店铺", "msku": "DEMO-LAMP-02", "sku": "DEMO-PRODUCT-02", "product_name": "阅读台灯（模拟商品）", "available": 0, "reserved": 3, "inbound": 60, "imported_at": now},
    ])


def downgrade():
    op.drop_table("demo_inventory")
