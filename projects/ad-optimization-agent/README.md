# 电商智能投放Agent

2026-11-10：正式开始独立从零搭建的深入主实战项目。完整规格见[SPEC.md](SPEC.md)。

- backend/：从环境、FastAPI接口、数据库到指标分析、RAG、审批、恢复及评估逐步实现。
- frontend/：独立前端目录，按投放分析、审批和任务页面逐步搭建。
- 当前已完成只读报表、规划执行、诊断评审，以及独立MySQL中的预算草案审批；图恢复、平台执行与用户页面继续逐块实现。
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

2026-11-11：analyze新增diagnosis，事实清单保留在answer。诊断Agent与评审Agent共享同一最小汇总快照，最多修订一次；状态为passed/needs_review/unavailable/skipped。正常含规划共3次Flash调用，修订最多增加2次；诊断评审阶段整体55秒。只诊断前10条候选，截断时明确提示；references为E编号到活动编号的本机映射。模型失败、无候选或任务不完整均保留事实结果，当前评审仅辅助参考，完整质量评测待补。

用户已于2026-11-11明确授权将汇总花费、归因销售额、ROAS与目标发送给已有Qwen供应商。诊断模型接收上述字段和临时E编号，账户编号/活动名称/日期/原始报表留在后端。goal文字继续按现有规划流程发送；真实数据只读。

## 预算草案与审批（2026-11-12）

在backend运行`.venv/Scripts/python.exe scripts/setup_business_db.py`，只初始化本机operations-mysql的ad_agent_business独立库，账号仅具草案表SELECT/INSERT/UPDATE与事件表SELECT/INSERT，凭据存忽略.env。初始DDL位于migrations/V001__budget_proposals.sql；未来表结构变更需新增迁移，当前初始化脚本仅CREATE IF NOT EXISTS。

- GET /health/business：业务库连通检查。
- POST /proposals：填写idempotency_key、profile_id、campaign_id、proposed_budget和reason，源预算/币种由只读源查询，草案与created事件同事务保存。
- GET /proposals、/proposals/detail?proposal_id=...：列表和详情，时间返回UTC。
- POST /proposals/decision：提交proposal_id、expected_version、decision(approve/reject)、reviewer；状态条件更新和审批事件同事务，旧版本/已处理/源预算变化409。
- GET /proposals/events?proposal_id=...：审计记录。

同一提交编号同内容返回同一草案，内容变化409；并发审批只允许一次状态迁移。source_budget为测试库快照，建议金额由用户填写。执行状态固定not_connected，平台修改接口及图级中断恢复后续接入；reviewer当前是本机演练填写标识，生产登录/审批权限接入后从服务端身份取得。教学验证记录已在自有库中留存，原因标注教学验证。

从固定模板配置backend/.env，源库账号信息保持本机。新环境先建立`.venv`并安装requirements-lock.txt。源库会话设置只读并限制查询执行时间，无建表或迁移操作。业务查询按账户/日期过滤，单页上限100；账户/活动ID用字符串，金额用Decimal，缺归因记录保持null。当前预算与报表预算分别返回。多用户身份与店铺授权在后续阶段接入；当前服务绑定本机127.0.0.1。
