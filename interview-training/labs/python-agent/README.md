# 电商Agent后端：当前目录与启动入口

2026-11-04整理。业务源码位于app，配置与依赖留项目根目录，迁移留migrations，独立实验留scripts。历史讲义中的平铺路径按下表对应，后续代码以本目录为准。

```text
python-agent/
├── app/
│   ├── main.py                       # 创建应用、登记接口
│   ├── api/                          # HTTP参数、响应与错误处理
│   │   ├── ads.py                    # 报表/工具预览/Agent对话
│   │   ├── inventory.py              # 库存查询与修改
│   │   ├── requirements.py           # 消息预览与结构化需求
│   │   └── health.py                 # 数据库健康检查
│   ├── schemas/                      # Pydantic输入/输出校验
│   │   ├── requirements.py
│   │   └── inventory.py
│   ├── services/llm_service.py        # 模型调用、工具循环
│   ├── tools/ad_tools.py              # 广告/ROAS/库存工具
│   ├── repositories/                 # 数据库查询和更新
│   │   ├── ad_repository.py
│   │   └── inventory_repository.py
│   ├── db/
│   │   ├── session.py                # engine连接池、数据库配置
│   │   └── models.py                 # SQLAlchemy表模型
│   └── prompts/requirements.py        # 提示词与消息组装
├── migrations/                       # Alembic迁移，版本编号保持
├── scripts/pool_demo.py               # 独立连接池实验
├── main.py                           # 兼容原main:app启动命令
├── alembic.ini
├── requirements.txt
├── requirements.lock.txt
└── .env                              # 本机配置，Git忽略
```

各Python目录的__init__.py声明包，日常修改对应业务文件即可。

在本目录PowerShell启动：

```powershell
.\dev.cmd
```

dev.cmd使用项目自己的Python，并自动定位项目目录，兼容当前PowerShell脚本限制；底层执行命令：

```powershell
.\.venv\Scripts\python.exe -u scripts\dev_server.py
```

数据库查看：DBeaver连接127.0.0.1:5432，数据库agent_training，用户名llm，密码读取本机.env的PG_PASSWORD。展开Schemas → public → Tables，打开表的Data页。ad_reports保存广告报表；inventory保存库存；conversations保存会话；messages保存用户和助手消息；task_events的details保存任务及工具结果。D08当前GET生成的card/selection响应在内存组装，其事实来源为ad_reports，UI响应本身尚未持久化。

同一个8000端口保持一个服务。旧uvicorn main:app仍可启动同一个应用。浏览器http://127.0.0.1:8000/docs，现按ads/inventory/requirements/health分组。

迁移命令保持：

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m alembic upgrade head
```

初始化和实验使用模块路径（在项目根目录执行）：

```powershell
.\.venv\Scripts\python.exe -m app.repositories.ad_repository
.\.venv\Scripts\python.exe -m scripts.pool_demo
.\.venv\Scripts\python.exe -m app.prompts.requirements
```

库存初始化的历史命令对应-m app.repositories.inventory_repository，当前数据库已经初始化；结构升级交给Alembic，历史初始化函数仅作课程查阅。

当前调用链：app.main登记api.ads → api.ads.ad_chat → services.llm_service.run_ad_tool → tools.ad_tools.inventory_tool → repositories.inventory_repository.get_inventory_from_db → db.session.engine → PostgreSQL。模型生成工具请求、后端执行查询、ToolMessage带回结果、模型组织回答。

配置加载：db/session.py和services/llm_service.py均定位python-agent根.env；环境变量已有值优先。数据库/模型凭据只留本机，不写进源码、日志或提交。

当前数据仍为synthetic_demo；user-001/store-A仍是后端固定本地身份。数据库查询和工具执行为真实本地运行，登录鉴权、授权外部业务API和线上交付按课程后续独立验收。


Development reload: dev.cmd watches app/**/*.py. Saving, adding and deleting Python files reloads the server automatically. Import errors can be corrected by saving again. Duplicate launches exit while the current manager keeps running. Ctrl+C stops the server tree. Restart after changing .env, dependencies or the launcher. Only identified servers from this project are cleaned; unrelated port owners remain running.
