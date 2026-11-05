# 运营提效助手

2026-11-05：独立从零搭建的较轻实战项目。

- backend/：从环境、FastAPI接口、数据库到库存巡检、SOP和日报逐步实现。
- frontend/：保留独立演示入口；当前业务页面计划接入公司已有Vue系统。
- backend/app按api、core、db、schemas、integrations、services、repositories划分职责；app/main.py统一装配。
- 已接入公司测试SSO与实时账号权限；登录返回本项目加密短期凭据，查询时复核公司会话与授权。
- 本机PostgreSQL独立库operations_assistant保存授权测试数据快照：stores、products、inventory_snapshots及data_imports；公司源库使用只读事务。
- 2026-11-05导入店铺385、商品11631、库存11489；27条库存缺少有效店铺映射，保留原始行，权限查询通过已授权店铺映射限制访问。
- 数据为一次性快照，带imported_at；自动同步、Vue页面、Agent工具、会话/任务/审批表及线上部署继续按业务逐项实施。
- 按真实上线标准增量交付；当前处于本机开发阶段，生产权限、容量指标、部署和验收分别记录。
- 数据源、外部接口授权、运行与部署证据按实际完成情况记录。

## 本地运行与文件职责

backend/dev.cmd启动http://127.0.0.1:8010/docs，入口为app.main:app。POST /api/v1/auth/login登录后，在Swagger Authorize中填返回的access_token；GET /api/v1/stores列出可访问店铺；GET /api/v1/inventory/{msku}?store_id=...按权限查询快照。

backend/.env保存本机配置并由Git忽略；DATABASE_URL为只读运行账号，MIGRATION_DATABASE_URL为独立迁移账号；MYSQL_*供人工导入脚本读取公司测试源库。账号密码、令牌及业务原始数据保持本机存储。

backend/migrations保存建表版本，执行`.venv\Scripts\python.exe -m alembic upgrade head`更新项目库结构。新环境先由数据库管理员创建operations_assistant和operations_migrator/operations_app专用登录角色，设置迁移角色为库所有者，授予运行角色CONNECT及public模式USAGE，撤销PUBLIC的CONNECT和模式CREATE；具体密码写入本机配置。

backend/scripts/import_test_snapshot.py执行首次导入；要求目标业务表为空，使用数据库事务和导入任务锁，写入数量与来源行数核对后一起提交。重复执行会停止并保留现有数据。后续数据刷新单独设计增量同步和失败恢复。

当前请求调用顺序：api/inventory.py → api/dependencies.py核验登录 → services/auth.py调用公司SSO核验当前权限 → repositories/inventory.py绑定授权范围 → db/session.py连接本项目库 → JSON响应。Agent工具后续调用同一业务查询，权限来自后端登录身份。
