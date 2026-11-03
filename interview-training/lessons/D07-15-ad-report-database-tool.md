# D07：广告报表入库，工具读取数据库。日期：11/03

对应原课5.1–5.3的业务数据持久化与用户隔离，串联D06工具执行。当前日历D13，实际D07；完整独立通过1/32。本块为教师候选与学生动手说明，学生业务文件保持原样。

目的：让GET /ads/report/{campaign_id}、广告查询工具、ROAS工具共用数据库报表。数据继续为synthetic_demo，数据库和查询是真实PostgreSQL；本地固定user-001/store-A仅用于演练，生产必须从已验证身份与可访问店铺取得作用域。库存工具本块仍为旧常量，单列待回接。

调用链：GET→main.ad_report→ad_tools.get_ad_report→ad_repository.get_ad_report_from_db→PostgreSQL；POST /ads/chat→run_ad_tool→模型选择工具→后端执行ad_report_tool或calculate_roas_tool→同一查询函数→ToolMessage→模型答复。模型仅提交campaign_id；用户身份和店铺由后端限定。

目标：必备为工具经后端查库、作用域过滤、迁移与HTTP失败映射；熟练为查询/计算共用函数和从返回结果定位来源；熟悉为金额Numeric与Python Decimal、日期及最近报表定义。

变更：models.py追加AdReport和三个导入；新迁移0003_ad_reports；新ad_repository.py；ad_tools仅替换get_ad_report；main替换ad_report并向ad_chat补数据库异常；llm_service将同步工具执行交给线程。

Numeric(12,2)为最多12位有效数字、2位小数的定点数列，默认读为Decimal；本块返回float维持原工具JSON数字契约，仅用于展示/比率，金额结算保持Decimal或整数分。Date读取date对象，isoformat变成YYYY-MM-DD文本。order_by(desc).limit(1)限定最近一期；不同日期分别存行，同店铺/活动/日期唯一。本表为单平台单口径日汇总，正式多平台要补平台/账号/归因窗口等键。

## 1 models.py追加（保留既有Store/Inventory）

```python
from datetime import date  # Python日期类型。
from decimal import Decimal  # Python精确十进制金额类型。
from sqlalchemy import Date, Numeric  # 新增数据库列类型。


class AdReport(Base):
    __tablename__ = "ad_reports"  # 新表名。
    __table_args__ = (
        UniqueConstraint("store_id", "campaign_id", "report_date", name="ad_reports_daily_key"),
        CheckConstraint("spend >= 0 AND attributed_sales >= 0", name="ad_reports_money_check"),
        CheckConstraint("clicks >= 0 AND impressions >= 0", name="ad_reports_counts_check"),
    )  # 每店铺每活动每天一条，金额和次数保持非负。

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    store_id: Mapped[str] = mapped_column(Text, ForeignKey("stores.id"), nullable=False)
    campaign_id: Mapped[str] = mapped_column(Text, nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    attributed_sales: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    data_source: Mapped[str] = mapped_column(Text, nullable=False)
```

## 2 新建migrations/versions/0003_ad_reports.py

```python
from alembic import op  # 已学过的迁移操作。
import sqlalchemy as sa

revision = "0003_ad_reports"
down_revision = "0002_inventory_version"  # 接在库存版本字段之后。
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_reports",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("store_id", sa.Text(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("campaign_id", sa.Text(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("spend", sa.Numeric(12, 2), nullable=False),
        sa.Column("attributed_sales", sa.Numeric(12, 2), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("data_source", sa.Text(), nullable=False),
        sa.UniqueConstraint("store_id", "campaign_id", "report_date", name="ad_reports_daily_key"),
        sa.CheckConstraint("spend >= 0 AND attributed_sales >= 0", name="ad_reports_money_check"),
        sa.CheckConstraint("clicks >= 0 AND impressions >= 0", name="ad_reports_counts_check"),
    )  # 迁移只管理表结构，样例数据单独初始化。


def downgrade() -> None:
    op.drop_table("ad_reports")  # 回退会删除此表和报表，已有业务数据时须先评估。
```

## 3 新建ad_repository.py

```python
from sqlalchemy import select, text  # ORM查询及参数化SQL。
from sqlalchemy.orm import Session
from db import engine  # 复用既有连接池。
from models import AdReport, Store


def initialize_ad_demo() -> None:
    with engine.begin() as connection:  # 两条样例一起提交，失败一起回滚。
        connection.execute(text("""
            INSERT INTO ad_reports
                (id, store_id, campaign_id, report_date, currency,
                 spend, attributed_sales, clicks, impressions, data_source)
            VALUES
                ('ad-A-20261021', 'store-A', 'AD-DEMO-001', '2026-10-21',
                 'CNY', 100, 250, 50, 5000, 'synthetic_demo'),
                ('ad-B-20261021', 'store-B', 'AD-DEMO-001', '2026-10-21',
                 'CNY', 900, 1800, 100, 8000, 'synthetic_demo')
            ON CONFLICT (store_id, campaign_id, report_date) DO NOTHING
        """))  # 重复执行保留已有报表；两家店的相同活动编号可并存。


def get_ad_report_from_db(user_id: str, store_id: str, campaign_id: str) -> dict | None:
    with Session(engine) as session:  # 本次查询结束时归还连接。
        statement = (
            select(AdReport)
            .join(Store, Store.id == AdReport.store_id)
            .where(
                Store.user_id == user_id,  # 店铺归属校验。
                AdReport.store_id == store_id,  # 当前选择的店铺。
                AdReport.campaign_id == campaign_id,  # 模型提供的业务编号。
            )
            .order_by(AdReport.report_date.desc())  # 日期从新到旧。
            .limit(1)  # 本接口固定读取该活动最近一期报表。
        )
        report = session.scalars(statement).one_or_none()  # 到这里才执行SQL。
        if report is None:
            return None  # 接口和工具分别处理未找到。
        return {
            "data_source": report.data_source,
            "store_id": report.store_id,
            "campaign_id": report.campaign_id,
            "report_date": report.report_date.isoformat(),  # date转日期文本。
            "currency": report.currency,
            "spend": float(report.spend),  # 保持原工具返回JSON数字的契约。
            "attributed_sales": float(report.attributed_sales),
            "clicks": report.clicks,
            "impressions": report.impressions,
        }


if __name__ == "__main__":
    initialize_ad_demo()  # 手动执行才初始化，import时跳过。
    print("广告合成样例已准备好；已有报表保持原值")
```

## 4 ad_tools.py新增导入，完整替换get_ad_report

```python
from ad_repository import get_ad_report_from_db  # 新增：数据库查询函数。


def get_ad_report(campaign_id: str) -> dict:
    report = get_ad_report_from_db(
        user_id="user-001",  # 本地演示身份；生产从验证后的登录状态传入。
        store_id="store-A",  # 本地演示店铺；后端应校验当前用户权限。
        campaign_id=campaign_id,  # 模型仅选择广告编号。
    )
    if report is None:
        raise ValueError("未找到可访问的广告报表")
    return report  # ad_report_tool与calculate_roas_tool继续复用此函数。
```

## 5 main.py替换ad_report，ad_chat补相同数据库异常

```python
from sqlalchemy.exc import TimeoutError as PoolTimeoutError  # 连接池等待超时。


@app.get("/ads/report/{campaign_id}")
def ad_report(campaign_id: str):
    try:
        return get_ad_report(campaign_id)  # 继续走原来的入口函数。
    except ValueError as error:
        raise HTTPException(404, "未找到可访问的广告报表") from error
    except (OperationalError, PoolTimeoutError) as error:
        raise HTTPException(503, "报表数据库暂时不可用") from error
    except SQLAlchemyError as error:
        raise HTTPException(500, "报表查询失败，请联系维护人员") from error
```

在ad_chat原有最后一个except后追加以下分支，原有模型超时/解析/供应商异常保留：

```python
    except (OperationalError, PoolTimeoutError) as error:
        raise HTTPException(503, "报表数据库暂时不可用") from error
    except SQLAlchemyError as error:
        raise HTTPException(500, "报表查询失败，请联系维护人员") from error
```

## 6 llm_service.py保持原工具循环，替换执行行

新增import asyncio。run_ad_tool原result = selected_tool.invoke(call["args"])替换为：

```python
                    result = await asyncio.to_thread(selected_tool.invoke, call["args"])
                    # 同步工具到线程中执行，async接口等待结果期间可处理其他请求。
```

to_thread接收函数及参数；线程中执行同步数据库操作，await取得结果或抛出异常。Session在工具线程内创建并关闭，engine进程共用。取消等待不会自动中止已执行的数据库查询；生产查询超时和容量限制后续联调，当前已有连接池5+0与等待上限。

## 动手命令与浏览器验收

项目目录执行：.venv\Scripts\python.exe -m alembic upgrade head → .venv\Scripts\python.exe -m alembic check → .venv\Scripts\python.exe ad_repository.py（执行两次验证幂等）。前提为原stores两条课程记录存在。

启动uvicorn main:app --reload --host 127.0.0.1 --port 8000；浏览器GET /ads/report/AD-DEMO-001读store-A/100/250及日期，未知编号404。Swagger POST /ads/chat输入“查询AD-DEMO-001最近一期报表，计算ROAS，说明报表日期和数据来源”，期望工具结果来源synthetic_demo、ROAS2.5，具体工具顺序由模型决定。重启后GET仍100/250，证明本地持久化。

可选因果验证：DBeaver事务中UPDATE ad_reports SET spend=125 WHERE store_id='store-A' AND campaign_id='AD-DEMO-001' AND report_date='2026-10-21' RETURNING *; 提交后新请求应125和ROAS2.0，样例日期保持不变；仅改已标记合成记录。每次POST请求新缓存，可读新值；同一次请求缓存可能复用旧快照。正式报表写入、归因口径、导入校验与授权外部API仍待后续。

必背：模型生成工具名称和参数，后端执行工具，查询函数按当前用户、店铺、活动编号读取数据库，结果回传模型组织答复。数据库存什么，工具读取什么；数据来源标记区分合成报表和真实业务报表。

面试答案：为何统一查询函数→HTTP查询与工具计算共享数据、权限与错误边界；为何重复初始化保留原值→唯一键识别同一期报表，冲突跳过防止覆盖后续修改；为何权限不放提示词→后端查询显式校验作用域，模型只能提供业务参数；钱如何存→Numeric定点数/Decimal或整数分，展示转换与结算精度分别设计。

待收学生证据：upgrade/check、GET100/250或本人修改后值、Agent工具结果与ROAS、重启后读取；D07其余任务/历史持久化及综合验收继续。原五表设计与Wiki模型保留后续对应D单元实作去向。
