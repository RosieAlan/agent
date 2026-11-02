from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass  # 所有表模型共用的基类，负责收集表结构信息。


class Store(Base):
    __tablename__ = "stores"  # 对应数据库里已有的stores表。

    id: Mapped[str] = mapped_column(
        Text, primary_key=True
    )  # 店铺编号，主键保证唯一。

    user_id: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 记录店铺属于哪个用户。

    name: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 店铺名称。


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

    id: Mapped[str] = mapped_column(
        Text, primary_key=True
    )  # 库存记录自身的编号。

    store_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("stores.id"),
        nullable=False,
    )  # 外键：这条库存必须属于一个已经存在的店铺。

    sku: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 商品编号。

    stock: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 当前库存。

    threshold: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 低库存预警阈值。

    data_source: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # 标记数据来源，当前为synthetic_demo。