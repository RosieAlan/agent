"""给库存表增加版本号。"""

from alembic import op  # Alembic提供的数据库结构操作工具。
import sqlalchemy as sa  # 用于描述列和数据类型。


revision = "0002_inventory_version"  # 本次版本号。
down_revision = "0001_inventory"  # 从已有初始版本继续升级。
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory",  # 给哪张表增加列。
        sa.Column(
            "version",       # 新列名称。
            sa.Integer(),    # 整数类型。
            nullable=False,  # 必须有值。
            server_default="1",  # 默认值为1。
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "inventory",
        "version",
    )  # 回退时删除这一列及其中保存的版本数据。