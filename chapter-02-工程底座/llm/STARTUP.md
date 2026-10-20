# 本地启动指南（Windows PowerShell）

本项目的启动顺序是：Docker Desktop → PostgreSQL → user-system → chat → chat-web。PostgreSQL 保存 `user_system` 和 `llm_chat` 两个数据库；前三个应用分别使用 4002、4001、3002 端口。下面的命令以当前练习项目为准。

## 1. 启动数据库

### D03/D04独立练习页：Docker暂不可用时的启动方式（2026-10-20验证）

当前`/d03`调用`/api/langchain/structured`，只组织提示词和调用模型，处理路径不查询业务数据库。2026-10-20实测数据库引擎未就绪期间，chat仍启动成功；健康检查200、非法数字输入400、前端练习页200。模型正常结果和用户取消由学生在页面验收。本结论适用于当前安装版本及该练习路径。

两个PowerShell窗口分别运行，保持窗口打开。Node先用`nvm use 22.19.0`切换，`node --version`确认v22；本次发现系统原先切回14，已纠正。

窗口1启动聊天后端：

```powershell
nvm use 22.19.0
cd 'C:\Users\Administrator\Desktop\newAgent\agent-course\chapter-02-工程底座\llm'
bun run dev:chat
```

看到`Chat running on :4001`后，窗口2启动前端：

```powershell
cd 'C:\Users\Administrator\Desktop\newAgent\agent-course\chapter-02-工程底座\llm'
bun run dev:chat-web
```

打开http://localhost:3002/d03，当前练习无需登录。登录、历史会话、文档检索等数据库功能继续按完整启动指南，待数据库恢复使用。每个端口保持一个进程，重启前在所属窗口按Ctrl+C。

本次教师已启动4001/3002；前端临时直接在clients/chat-web执行`bun x next dev --port 3002`以便先查看页面。该命令跳过脚本中的4001等待，前后端都就绪后操作练习。日常采用上面两个窗口的命令。

先打开 Docker Desktop，等它显示引擎运行。PowerShell 中检查：

```powershell
docker desktop status
docker version --format '{{.Server.Version}}'
```

若 Docker Desktop 还没打开，可执行 `docker desktop start`，再重复上面的检查。`docker version` 能输出服务端版本，说明 Docker 引擎可用。仅看到 Docker Desktop 窗口或客户端版本，并不足以证明引擎已经可用。

本机已有课程专用容器 `llm-postgres`，直接启动：

```powershell
docker start llm-postgres
docker exec llm-postgres pg_isready
docker ps --filter 'name=llm-postgres'
```

成功时，`pg_isready` 显示 `accepting connections`，`docker ps` 显示 `Up` 和 `5432->5432/tcp`。这个容器使用 `pgvector/pgvector:pg16` 镜像。`llm_chat` 和 `user_system` 都在容器内，聊天库已启用 `vector` 扩展。可按需核对：

```powershell
docker exec llm-postgres psql -U llm -d llm_chat -tAc 'SELECT current_database();'
docker exec llm-postgres psql -U llm -d user_system -tAc 'SELECT current_database();'
docker exec llm-postgres psql -U llm -d llm_chat -tAc "SELECT extname FROM pg_extension WHERE extname='vector';"
```

数据库文件保存在 Docker 卷 `llm-pgdata` 中。停止容器或重启电脑后，再执行 `docker start llm-postgres` 即可继续使用原有数据。请保留这个容器和卷，尤其避免运行 `docker rm -v llm-postgres` 或 `docker volume rm llm-pgdata`。

## 2. 启动三个应用

日常使用推荐一个终端启动全部应用。先启动上面的数据库，确认原有 4001、4002、3002 应用已在各自终端按 Ctrl+C 退出，然后执行：

```powershell
cd "C:\Users\Administrator\Desktop\newAgent\agent-course\chapter-02-工程底座\llm"
bun run dev:app
```

此命令同时启动用户服务、聊天服务和前端。看到三个服务就绪后打开 <http://localhost:3002>。这个终端保持运行；按 Ctrl+C 可以结束本次一起启动的应用。已经启动服务时保留当前进程，避免重复执行造成端口占用。

分别调试时，可按以下方式使用三个终端：

打开三个独立的 PowerShell 窗口。每个窗口都先进入同一个项目目录：

```powershell
cd "C:\Users\Administrator\Desktop\newAgent\agent-course\chapter-02-工程底座\llm"
node --version
```

本项目使用 Node 22。版本不对时，先执行 `nvm use 22.19.0`。然后按顺序启动，保留各窗口运行：

| 窗口 | 命令 | 成功标志 |
|---|---|---|
| 1：登录服务 | `bun run dev:user` | `User System running on port 4002` |
| 2：聊天服务 | `bun run dev:chat` | `Chat running on :4001` |
| 3：前端 | `bun run dev:chat-web` | 浏览器打开 <http://localhost:3002> |

前端脚本会等待 4001 端口，因此先启动 chat 再启动前端。这里的 `bun run dev` 只负责 chat 和 chat-web；登录服务仍需单独运行 `bun run dev:user`。

应用配置分别在 `services/user-system/.env`、`services/chat/.env` 和 `packages/database/.env`。当前配置都连接本机 5432：聊天服务使用 `llm_chat`，登录服务使用 `user_system`。这些文件含凭据，排查时只核对主机、端口、数据库名及 JWT 配置，避免把完整连接串、密钥和 Token 发到聊天或终端日志中。

## 3. 检查是否启动成功

```powershell
docker exec llm-postgres pg_isready
Get-NetTCPConnection -LocalPort 5432,4002,4001,3002 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalPort,OwningProcess
```

预期四个端口都处于监听状态。在浏览器打开 <http://localhost:3002>，使用课程账号登录，点击“新建会话”，输入需求后发送。页面会自动创建会话、携带登录凭证、展示真实分析进度及报告。左侧会话列表可以读取原有历史；“刷新历史”可以找回此前请求超时后已落库的报告。

种子账号为 `admin`，密码为 `Admin@123456`。浏览器端访问同一个 3002 地址，前端服务在内部调用 4002 用户服务和 4001 聊天服务。登录令牌存入 HttpOnly Cookie，后续请求自动携带。退出登录会清除当前浏览器会话；令牌过期后页面提示重新登录。

Apifox 保留为接口排查工具。手动调用时，请求头格式是 `Authorization: Bearer <accessToken>`，`Bearer` 与 Token 中间有一个空格。

## 4. 常见问题

| 现象 | 处理 |
|---|---|
| `Docker Desktop is unable to start` | 执行 `docker desktop status` 和 `docker version`；等待引擎启动。仍显示停止时，在 Docker Desktop 中检查启动状态，再执行 `docker desktop restart`。引擎可用后重试 `docker start llm-postgres`。 |
| `EADDRINUSE`，端口 4001、4002 或 3002 被占用 | 用 `Get-NetTCPConnection -LocalPort 4001 -State Listen` 查看占用进程；确认是旧的课程服务后，在它的原终端按 `Ctrl+C`，然后重新启动。把命令中的端口换成实际报错端口。 |
| 前端一直等候 | 先确认 chat 日志出现 `Chat running on :4001`，再运行 `bun run dev:chat-web`。 |
| 数据库连接失败 | 先检查 `docker exec llm-postgres pg_isready`，再核对对应 `.env` 中的 `DATABASE_URL` 主机、端口和数据库名。 |
| 登录成功但 chat 返回 401 | 检查 Apifox 的 Bearer Token；chat 与 user-system 必须使用相同的 `JWT_SECRET`。 |
| 修改 `.env` 或 `services/chat/config/langchain.yaml` 后没生效 | 在对应应用的窗口按 `Ctrl+C`，重新运行启动命令。 |

结束练习时，在三个应用窗口分别按 `Ctrl+C`。需要停止数据库时执行 `docker stop llm-postgres`；下次按本文第 1 节重新启动。项目的 `infra/compose` 目录目前没有可运行的 Compose 文件，因此此处使用已有的 `llm-postgres` 容器。

## 5. 真实需求分析工作区（2026-10-15 接入）

日常操作入口为 <http://localhost:3002>：登录 → 新建会话 → 输入需求 → 观察进度 → 阅读报告。新会话在首次发送时自动创建。已有会话从左侧选择，消息会从 PostgreSQL 读取；补充追问信息时直接在同一会话继续发送。

端口职责：3002 提供用户页面和同源接口代理；4002 验证账号、签发和撤销登录会话；4001 执行文档检索、LangGraph 专家分析及消息持久化。后台服务在开发环境分端口运行，用户统一在 3002 操作。

真实分析采用 `POST /api/conversations/:id/chat/stream`。后端验证会话归属后立即建立 SSE 连接，推送检索、提取、澄清、专家选择、各专家、风险和汇总的运行状态；每 10 秒发送心跳，最终用 done 事件返回结果。该实现按节点展示进度，报告在完成时整包显示。

一次分析包含多次模型调用，实际耗时取决于当前模型供应商。总时限为 10 分钟；“停止分析”或关闭页面会发送取消信号，支持该信号的模型调用会中止。数据库检索和本地嵌入等不可取消操作可能继续到当前操作结束。停止后可以刷新历史，查看已经保存的消息。

用户输入在模型分析前保存；助手回复、追问、专家名单和专家结论在结果产生后保存到 messages 及 metadata。旧消息中缺少的专家明细继续按原有正文显示。第六章 UI 组件练习保留在 <http://localhost:3002/ui-demo>，入口也位于工作区左下角。

主要文件：

- `clients/chat-web/src/app/page.tsx`：登录、会话切换、需求输入、进度与报告。
- `clients/chat-web/src/app/workbench-client.ts`：请求和 SSE 分帧解析。
- `clients/chat-web/src/app/api/workbench/[...path]/route.ts`：同源登录代理、HttpOnly Cookie、业务接口代理。
- `services/chat/src/conversation/conversation.controller.ts`：鉴权后的分析流接口。
- `services/chat/src/llm/analysis-progress.ts`：真实阶段状态与取消检查。
- `services/chat/src/llm/advanced-analysis.service.ts`：历史、检索、图调用和消息保存。

页面代码通常自动热更新；后端 watch 会重新编译。页面仍显示旧内容时按 Ctrl+F5。启动或重启仍按第 2 节在自己的终端执行，每个端口保持一个服务进程。

## 6. 本次验证记录（2026-10-15）

- 真实浏览器验证：登录、创建会话、发送需求、节点进度、三个专家结论与最终报告均已跑通；本轮模型分析约两分多钟。
- 历史恢复验证：原超时会话的四条消息可以读取，刷新后内容保留；手机 390px 宽度显示正常；退出登录后接口返回 401。
- 自动验证：新增后端回归检查 8 项通过，后端完整测试结果为 10 项通过、1 项跳过；前端代理与 SSE 解析检查 8 项通过。
- chat 与 chat-web 类型检查通过，前后端构建通过。临时测试文件、浏览器脚本和独立编译目录已清理，原有测试保留。
- 页面截图保存在 `../../chapter-09-LangGraph多Agent/artifacts/`，包括 `workbench-login.png`、`workbench-report.png`、`workbench-mobile.png`。
