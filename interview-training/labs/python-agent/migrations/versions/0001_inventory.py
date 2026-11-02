"""店铺与库存表的初始结构。"""

from alembic import op
import sqlalchemy as sa

revision = "0001_inventory"  # 当前版本号。
down_revision = None  # 第一个版本，没有上一个版本。
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
    )  # 先创建被库存表引用的店铺表。
    op.create_table(
        "inventory",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("store_id", sa.Text(), nullable=False),
        sa.Column("sku", sa.Text(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("data_source", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="inventory_store_id_fkey"
        ),
        sa.UniqueConstraint(
            "store_id", "sku", name="inventory_store_id_sku_key"
        ),
        sa.CheckConstraint("stock >= 0", name="inventory_stock_check"),
        sa.CheckConstraint("threshold >= 0", name="inventory_threshold_check"),
    )  # 迁移管理结构；课程样例数据仍由单独初始化命令管理。


def downgrade() -> None:
    # 回退这个初始版本会删除业务表及其中数据。
    # 只在确认可丢弃的测试环境演练。
    op.drop_table("inventory")  # 先删除引用其他表的库存表。
    op.drop_table("stores")
