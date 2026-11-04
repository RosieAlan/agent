from alembic import op  # Alembic提供的数据库结构操作。
import sqlalchemy as sa  # 描述数据库列和约束。


revision = "0003_ad_reports"  # 本次迁移编号。
down_revision = "0002_inventory_version"  # 接在上次库存版本迁移之后。
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_reports",  # 创建广告报表表。

        sa.Column("id", sa.Text(), primary_key=True),

        sa.Column(
            "store_id",
            sa.Text(),
            sa.ForeignKey("stores.id"),
            nullable=False,
        ),

        sa.Column("campaign_id", sa.Text(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),

        sa.Column("spend", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "attributed_sales",
            sa.Numeric(12, 2),
            nullable=False,
        ),

        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("data_source", sa.Text(), nullable=False),

        sa.UniqueConstraint(
            "store_id",
            "campaign_id",
            "report_date",
            name="ad_reports_daily_key",
        ),  # 防止同一期报表重复。

        sa.CheckConstraint(
            "spend >= 0 AND attributed_sales >= 0",
            name="ad_reports_money_check",
        ),

        sa.CheckConstraint(
            "clicks >= 0 AND impressions >= 0",
            name="ad_reports_counts_check",
        ),
    )


def downgrade() -> None:
    op.drop_table("ad_reports")  # 回退会删除这张表及其中的报表。