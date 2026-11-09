from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from datetime import date  # Python的日期类型。
from decimal import Decimal  # Python的精确十进制数类型。
from sqlalchemy import Date, Numeric  # 数据库的日期、定点小数列。
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Identity, Index, func
from sqlalchemy.dialects.postgresql import JSONB

class Base(DeclarativeBase):
    pass  # 所有表模型共用的基类，负责收集表结构信息。


class Store(Base):
    __tablename__ = "stores"  # 对应数据库里已有的stores表。

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # 店铺编号，主键保证唯一。

    user_id: Mapped[str] = mapped_column(Text, nullable=False)  # 记录店铺属于哪个用户。

    name: Mapped[str] = mapped_column(Text, nullable=False)  # 店铺名称。


class Inventory(Base):
    __tablename__ = "inventory"  # 对应已有的inventory表。

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "sku",
            name="inventory_store_id_sku_key",
        ),  # 同一店铺的同一SKU只保存一条库存记录。
        CheckConstraint(
            "stock >= 0",
            name="inventory_stock_check",
        ),  # 数据库要求库存大于等于0。
        CheckConstraint(
            "threshold >= 0",
            name="inventory_threshold_check",
        ),  # 库存预警阈值也要求大于等于0。
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # 库存记录自身的编号。

    store_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("stores.id"),
        nullable=False,
    )  # 外键：这条库存必须属于一个已经存在的店铺。

    sku: Mapped[str] = mapped_column(Text, nullable=False)  # 商品编号。

    stock: Mapped[int] = mapped_column(Integer, nullable=False)  # 当前库存。

    threshold: Mapped[int] = mapped_column(Integer, nullable=False)  # 低库存预警阈值。

    data_source: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 标记数据来源，当前为synthetic_demo。

    version: Mapped[int] = mapped_column(
        Integer,  # 数据库使用整数类型。
        nullable=False,  # 每条记录必须有版本号。
        server_default="1",  # 数据库默认填1。
    )


class AdReport(Base):
    __tablename__ = "ad_reports"  # 对应数据库里的广告报表表。

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "campaign_id",
            "report_date",
            name="ad_reports_daily_key",
        ),  # 同一家店、同一个活动、同一天只能保存一条报表。
        CheckConstraint(
            "spend >= 0 AND attributed_sales >= 0",
            name="ad_reports_money_check",
        ),  # 花费和归因销售额必须为非负数。
        CheckConstraint(
            "clicks >= 0 AND impressions >= 0",
            name="ad_reports_counts_check",
        ),  # 点击次数和展示次数必须为非负数。
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # 报表记录自身的唯一编号。

    store_id: Mapped[str] = mapped_column(
        Text, ForeignKey("stores.id"), nullable=False
    )  # 报表属于哪家店；店铺必须已经存在。

    campaign_id: Mapped[str] = mapped_column(Text, nullable=False)  # 广告活动编号。

    report_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )  # 这份报表统计的是哪一天。

    currency: Mapped[str] = mapped_column(Text, nullable=False)  # 币种，例如CNY。

    spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # 广告花费。

    attributed_sales: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )  # 按当前报表归因口径计算的销售额。

    clicks: Mapped[int] = mapped_column(Integer, nullable=False)  # 点击次数。

    impressions: Mapped[int] = mapped_column(Integer, nullable=False)  # 展示次数。

    data_source: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 当前仍标记为synthetic_demo。

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        Text, primary_key=True
    )  # 会话编号。

    user_id: Mapped[str] = mapped_column(
        Text, nullable=False, index=True
    )  # 会话属于哪个用户。

    title: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 会话标题。

    active_task_id: Mapped[str | None] = mapped_column(
        Text
    )  # 当前执行的任务；None表示空闲。

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )  # 数据库填写创建时间。


class Message(Base):
    __tablename__ = "messages"

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="messages_role_check",
        ),
        Index(
            "messages_conversation_id_id_idx",
            "conversation_id",
            "id",
        ),  # 按会话查询消息，再按编号排序。
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )  # 数据库自动生成顺序编号。

    conversation_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )  # 关联所属会话。

    task_id: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 关联本轮执行。

    role: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # user或assistant。

    content: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 消息正文。

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class TaskEvent(Base):
    __tablename__ = "task_events"

    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'completed', 'limit_reached', 'failed')",
            name="task_events_status_check",
        ),
        UniqueConstraint(
            "task_id",
            "status",
            name="task_events_task_status_key",
        ),
        Index(
            "task_events_conversation_id_id_idx",
            "conversation_id",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True
    )

    conversation_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    task_id: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 同一轮执行的事件共用这个编号。

    status: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 开始、完成、达到上限、失败。

    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )  # 工具记录或安全错误码。

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
