# 电商智能投放Agent

2026-11-10：正式开始独立从零搭建的深入主实战项目。完整规格见[SPEC.md](SPEC.md)。

- backend/：从环境、FastAPI接口、数据库到指标分析、RAG、审批、恢复及评估逐步实现。
- frontend/：独立前端目录，按投放分析、审批和任务页面逐步搭建。
- 当前已完成独立后端的只读广告账户/日报查询与指标计算，数据来自授权公司测试库；Agent诊断和前端继续逐块实现。
- 数据源、外部接口授权、运行与部署证据按实际完成情况记录。

完整项目名：电商智能投放与多Agent创作平台。投放分析/方案审批执行与多模态创作两条主线共同保留，首条功能先实现广告数据校验与指标接口，后续接规划执行、长任务、多Agent、成员/@角色、素材校验、记忆及实时交付。

## 本机运行（2026-11-10）

在backend目录执行`dev.cmd`（PowerShell使用`.\dev.cmd`），独立Python虚拟环境启动8030，监视app目录热更新。接口文档：http://127.0.0.1:8030/docs。

- GET /health/source：实际检查数据源连接和只读会话。
- GET /ads/profiles?limit=50：广告账户、国家、币种与时区。
- GET /ads/reports?profile_id=68872684445005&start_date=2024-07-31&end_date=2024-07-31：单账户最多31天的SP日报，可选campaign_id、归因窗口1/7/14/30、limit和offset。
- POST /assistant/plan：接收goal和scope，调用qwen3.8-flash预览任务清单。支持query_reports/find_low_roas/write_review；后端校验操作、参数和依赖。模型接收goal及固定虚构scope，真实表单范围由后端填入。该接口仅生成计划，实际执行使用/assistant/execute或合并入口/assistant/analyze。
- POST /assistant/execute：提交TaskPlan，按依赖循环执行只读查询、活动汇总/低ROAS筛选、事实复盘，返回execution_order和各任务状态/结果/耗时。执行阶段只用本机代码，无模型调用。结果有后续页或offset非零时阻止汇总分析，提示缩小范围；当前每页最多100条。任务结果本轮保存在内存，数据库持久化/恢复/Replan后续实现。
- POST /assistant/analyze：主入口，提交goal/scope后一次完成规划、校验、执行及事实复盘，返回plan与ExecutionResponse。同步执行器由asyncio.to_thread运行。规划时scope使用固定虚构模板，模型返回后由后端填入表单中的真实账户、日期与分页范围；用户goal文字仍会发送至模型。结果目前只在单次请求内保存，复盘为程序事实清单。

从固定模板配置backend/.env，源库账号信息保持本机。新环境先建立`.venv`并安装requirements-lock.txt。源库会话设置只读并限制查询执行时间，无建表或迁移操作。业务查询按账户/日期过滤，单页上限100；账户/活动ID用字符串，金额用Decimal，缺归因记录保持null。当前预算与报表预算分别返回。多用户身份与店铺授权在后续阶段接入；当前服务绑定本机127.0.0.1。
