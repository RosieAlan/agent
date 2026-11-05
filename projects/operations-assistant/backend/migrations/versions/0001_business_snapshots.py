"""Create the local MySQL project's initial business snapshot tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = "0001_business_snapshots"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stores",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.Text()),
        sa.Column("account_code", sa.String(255)),
        sa.Column("country", sa.Text()),
        sa.Column("status", sa.Integer()),
        sa.Column("imported_at", DATETIME(fsp=6), nullable=False), mysql_engine="InnoDB")
    op.create_index("ix_stores_account_code", "stores", ["account_code"])
    op.create_table("products",
        sa.Column("source_id", sa.String(64), primary_key=True),
        sa.Column("sku", sa.String(255)),
        sa.Column("name", sa.Text()),
        sa.Column("brand", sa.Text()),
        sa.Column("category", sa.Text()),
        sa.Column("source_updated_at", DATETIME(fsp=6)),
        sa.Column("imported_at", DATETIME(fsp=6), nullable=False), mysql_engine="InnoDB")
    op.create_index("ix_products_sku", "products", ["sku"])
    op.create_table("inventory_snapshots",
        sa.Column("source_id", sa.String(64), primary_key=True),
        sa.Column("store_id", sa.String(64)),
        sa.Column("account", sa.String(255)),
        sa.Column("msku", sa.String(255)),
        sa.Column("sku", sa.String(255)),
        sa.Column("asin", sa.Text()),
        sa.Column("available", sa.BigInteger()),
        sa.Column("reserved", sa.BigInteger()),
        sa.Column("inbound", sa.BigInteger()),
        sa.Column("source_updated_at", DATETIME(fsp=6)),
        sa.Column("imported_at", DATETIME(fsp=6), nullable=False), mysql_engine="InnoDB")
    # 保留原始行；来源缺失店铺映射的记录会在导入审计中计数。
    op.create_index("ix_inventory_store_msku", "inventory_snapshots", ["store_id", "msku", "account"])
    op.create_table("data_imports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("imported_at", DATETIME(fsp=6), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False), mysql_engine="InnoDB")


def downgrade():
    for name in ["data_imports", "inventory_snapshots", "products", "stores"]:
        op.drop_table(name)
