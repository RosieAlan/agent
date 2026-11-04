# 当前Python项目布局

本文件继承工作区和agent-course学习规则。2026-11-04起，先读本目录README.md理解当前文件位置。

- HTTP入口app/main.py，路由app/api，Pydantic校验app/schemas，模型与工具循环app/services/llm_service.py，工具app/tools/ad_tools.py，数据库读写app/repositories，连接池app/db/session.py，表模型app/db/models.py，提示词app/prompts，独立实验scripts，迁移migrations。
- 所有内部导入使用app开头的完整模块路径，独立实验按项目根目录python -m模块运行。
- .env保持python-agent根目录并被Git忽略；移动配置读取文件时校对根目录定位，保护本机凭据。
- 新增教学说明使用真实当前路径和函数名；旧平铺讲义属于历史，README提供迁移对应。
- 本次只整理现有职责，数据库结构、业务数据、已有HTTP路径和学生实现保留。root main.py仅兼容旧启动命令。
