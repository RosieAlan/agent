# D07-05 ORM查询现有库存（2026-11-02）
原课5.3 Prisma模型与查询映射到SQLAlchemy，迁移仍为下一块。授课交付在对话，学生实现业务文件。
当前调用：GET /inventory/{sku} → main.inventory_detail → inventory_repository.get_inventory_from_db → Session(engine) → PostgreSQL → 字典 → JSON。
新增models.py；仓储顶部增加select、Session、Store/Inventory导入，仅替换get_inventory_from_db；main、db、更新函数和初始化函数沿用。
Mapped为ORM字段类型声明；mapped_column配置真实列；Base收集表定义；Session为单次数据库操作上下文，与用户聊天会话分别管理。
select/join/where构造查询，session.scalars执行，one_or_none返回零个或一个对象；多条抛异常暴露数据问题。Session关闭前转换字典，with归还连接。engine按进程共享，Session按调用创建。现有同步HTTP路由继续同步数据库访问。
模型使用Text对齐既有TEXT字段，保留外键/唯一/非负约束。导入模型只注册结构；表结构变更后续通过Alembic审查迁移。
固定user-001/store-A为当前本地身份；后续从服务端认证和店铺授权取得；Agent工具尚未回接数据库，当前仍常量库存12。

## models.py完整候选
```python
from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass  # 所有表模型共用的基类，负责收集表结构信息。


class Store(Base):
    __tablename__ = "stores"  # 对应现有店铺表。

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Inventory(Base):
    __tablename__ = "inventory"  # 对应现有库存表。
    __table_args__ = (
        UniqueConstraint("store_id", "sku", name="inventory_store_id_sku_key"),
        CheckConstraint("stock >= 0", name="inventory_stock_check"),
        CheckConstraint("threshold >= 0", name="inventory_threshold_check"),
    )  # 保留同店铺商品唯一、库存和阈值非负的约束。

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    store_id: Mapped[str] = mapped_column(
        Text, ForeignKey("stores.id"), nullable=False
    )  # 库存必须关联已有店铺。
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    data_source: Mapped[str] = mapped_column(Text, nullable=False)
```

## inventory_repository.py导入增量
```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import Store, Inventory
```

## 替换查询函数
```python
def get_inventory_from_db(
    user_id: str, store_id: str, sku: str
) -> dict | None:
    """读取指定用户所属店铺的一条库存记录。"""
    with Session(engine) as session:  # 本次查询使用独立Session，结束时关闭。
        statement = (
            select(Inventory)  # 准备查询库存模型，此处尚未访问数据库。
            .join(Store, Store.id == Inventory.store_id)  # 关联店铺归属。
            .where(
                Store.user_id == user_id,  # 用户只能读取自己的店铺。
                Inventory.store_id == store_id,
                Inventory.sku == sku,
            )
        )
        item = session.scalars(statement).one_or_none()  # 执行SQL，返回对象或None。
        if item is None:
            return None  # 交给main.py转换为404。
        return {
            "data_source": item.data_source,  # 访问对象属性取得数据库字段。
            "store_id": item.store_id,
            "sku": item.sku,
            "stock": item.stock,
            "threshold": item.threshold,
            "is_low_stock": item.stock < item.threshold,
        }  # 在Session关闭前组装普通字典，由FastAPI转换成JSON。
```

## 验证与边界
教师在真实PG只读验证候选：A店库存25/阈值20/低库存false，B店88，跨用户查询None，缺SKU None，注入式SKU无命中，列类型/空值要求匹配现有表，查询后连接占用0；未改表、未写库存、模型API调用0次。学生接入后的Swagger证据待交。
浏览器GET /inventory/SKU-DEMO-001应保留stock25；GET不存在SKU应404。负数请求仍由既有PATCH输入校验处理。
必背：ORM将表结构映射为类，将记录映射为对象；查询条件仍须限定用户、店铺、商品，数据库约束继续负责完整性。engine管理连接，Session管理一次数据库操作过程；模型定义描述结构，Alembic记录并执行结构变更。
生产后续：真实身份、审计、并发更新、索引/执行计划、迁移及发布、备份恢复仍待落地。

