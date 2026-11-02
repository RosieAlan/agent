# D07-06 Alembic初始版本与已有数据库接入（2026-11-02）

对应原5.3 Prisma迁移目标，使用Alembic1.20.1/SQLAlchemy2.1.6。工具配置由教师准备，学生通过命令验证版本和模型差异并解释职责。新增alembic.ini、migrations/env.py、script.py.mako、versions/0001_inventory.py；依赖写入requirements及锁文件。db/main/仓储/模型保持原样，模型供应商调用0次。

调用：python -m alembic current/check/upgrade → alembic.ini定位migrations → env.py复用db.engine与models.Base.metadata → PostgreSQL和版本脚本。浏览器库存查询沿用原入口。
env online意为连接数据库执行；offline --sql意为生成SQL文本，和服务器部署地域分别管理。
revision当前版本；down_revision前一版本；upgrade升级结构；downgrade回退结构。初始版本downgrade删除库存与店铺表，只在可丢弃测试环境演练。head表示迁移目录的最新版本（当前单分支）。
stamp只登记版本，upgrade执行结构操作；已有表接入前需核对与具体版本匹配。此次先在事务临时schema真实执行初始建表，再比较两表列顺序/类型/nullable/default/主键/唯一/外键/非负check，与现有表一致后stamp具体0001_inventory。正式课程库业务表和数据未变，仅新增版本表及记录。首次current命令会连接数据库，可能创建版本管理表，库存读取单独验证。

## 核心env.py
```python
from logging.config import fileConfig

from alembic import context
from db import database_url, engine  # 复用.env配置，密码留在本机。
from models import Base  # 导入并登记Store、Inventory模型。

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)  # 加载迁移命令的日志配置。

target_metadata = Base.metadata  # 自动比较时使用的目标表结构。


def configure_and_run(connection) -> None:
    context.configure(
        connection=connection,  # 本次迁移实际使用的数据库连接。
        target_metadata=target_metadata,
        compare_type=True,  # 比较模型和数据库的字段类型。
    )
    with context.begin_transaction():  # 支持事务的DDL由事务保护。
        context.run_migrations()  # 按版本关系执行迁移操作。


def run_migrations_online() -> None:
    # 测试或部署脚本可以传入已有连接，以便统一控制事务。
    connection = config.attributes.get("connection")
    if connection is not None:
        configure_and_run(connection)
    else:
        with engine.connect() as connection:  # 普通命令从连接池获取连接。
            configure_and_run(connection)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,  # 用于生成SQL，连接配置不写入Git配置文件。
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()  # --sql模式只输出SQL，供发布前审查。


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

## 初始迁移完整文件
```python
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
```

## 学生执行
在python-agent目录：
```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
```
预期0001_inventory(head)及No new upgrade operations detected。GET /inventory/SKU-DEMO-001仍25/20/false。
check使用自动比较器范围，数据事实/业务权限/未启用的check与默认值比较另外验证。

## 教师验证
pip check通过；临时schema初始upgrade→结构对照→check→downgrade→再次upgrade通过，事务回滚后schema消失。课程库核对无差异后stamp具体初始版本，再check通过，库存全行前后相等。CLI版本和HTTP读取另行验证。临时测试脚本以stdin执行，未保留文件。
Windows生成ini中的中文注释触发locale GBK解码失败，改ASCII配置注释后命令正常；Python源码继续UTF8中文注释。
权限仍为固定本地演示身份，迁移/runtime数据库分权、发布备份、实际线上部署仍待对应实作。迁移文件结构演示以合成课程数据为准。

## 必背
ORM模型定义目标表结构；迁移脚本保存结构变更步骤；alembic_version保存当前迁移版本。生成候选后审查、测试环境验证、发布任务执行迁移，再验证应用和已有数据。已有库先核对结构与基线匹配再stamp；新空库通过upgrade建表。
下一块新增version列并处理旧数据与发布兼容，随后并发更新、索引及既定D07模型内容。

