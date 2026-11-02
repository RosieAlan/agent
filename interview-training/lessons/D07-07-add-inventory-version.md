# D07-07 实际新增库存version字段（2026-11-02）
学生实作，教师候选验证；原5.3迁移落地。主线仅增加version列并在原GET返回。
先停本地uvicorn，修改models.Inventory最后加version Mapped[int] Integer nullableFalse server_default"1"，新建migrations/versions/0002_inventory_version.py，最后查询返回字典增加version:item.version。其他函数尤其更新函数完整保留。
```python
"""给库存表增加版本号。"""
from alembic import op  # 数据库结构操作工具。
import sqlalchemy as sa  # 描述列和数据类型。

revision = "0002_inventory_version"  # 本次升级的版本号。
down_revision = "0001_inventory"  # 在现有初始版本上升级。
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory",  # 修改库存表。
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",  # 数据库给已有记录和后续省略此字段的记录填1。
        ),
    )


def downgrade() -> None:
    op.drop_column("inventory", "version")  # 回退会删除这一列及其中版本数据。
```
op.add_column将Column定义转换为ALTER TABLE ADD COLUMN；server_default为数据库默认值，已有行获得1，以后INSERT省略此字段也用1。版本号列为下一块并发控制准备，本轮更新函数尚未递增或比较版本。
命令：python -m alembic upgrade head；python -m alembic current；python -m alembic check；用项目虚拟环境解释器运行。head为当前单分支最新版本。升级成功后再启动uvicorn，GET预期stock25/threshold20/false/version1。
本地停服后修改是教学简化；生产通常先增加兼容旧代码的列，再发布依赖新列的应用，评估DDL锁等待并验证备份恢复。downgrade会删除version列及数据，本轮只解释，回退演练在隔离环境进行。
教师真实PG事务临时schema验证已有stock25保留、已有行version1、新插入省略version得1、downgrade后stock25保留、再次upgrade通过；事务回滚后临时schema消失。实际课程库仍初始版本、无version列、原库存数据前后相等，模型调用0次。学生接入与升级输出待交。
必背：模型增加字段描述Python期望的表结构；迁移执行ALTER TABLE实际升级数据库；接口读取新字段并返回。新增字段时同时考虑已有记录取值和旧应用兼容性。

