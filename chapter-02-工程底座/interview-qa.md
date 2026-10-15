# 第二章面试题 & 答案

### Q1：为什么一开始就选 monorepo？
跨层的接口定义（类型、DTO、schema）会同时出现在前端、后端、共享层。多仓库下改一个字段要分别改代码、分别发版，中间存在版本对不上的兼容窗口；monorepo 一次提交就能改完。另外共享包不用"发布→安装"，直接引用本地代码；以后项目变多也不用做仓库级迁移。

### Q2：monorepo 的代价是什么？
目录划分、依赖边界、任务编排这些规则必须提前定好。课程称之为"把复杂度提前显式化"——这些问题用哪种方式都绕不开，多仓库只是把它们分散隐藏了。

### Q3：Bun / Next / Nest / Turbo / Compose 各解决什么？
- Bun：运行 TS/JS + 安装依赖 + 管理 workspaces（替代 Node + npm/pnpm）
- Next：网页前端，monorepo 下可直接消费共享包
- Nest：服务端，模块化 + 依赖注入，承接持续增长的能力
- Turbo：任务图（谁先谁后）、增量执行、缓存复用
- Compose：把多个服务当成一个系统启动，管端口、顺序、环境变量

### Q4：为什么智能体系统的复杂度主要堆在服务端？
模型调用、工具调用、RAG、Agent 运行时都在后端，还要用 API Key、连数据库、调外部服务，不能放在浏览器里（放前端 Key 就暴露了）。前端只负责收集输入和展示结果。

### Q5：Bun 和 pnpm 的主要区别？学习成本在哪？
pnpm 只是包管理器，代码仍由 Node 运行；Bun 是运行时 + 包管理器 + 打包 + 测试，底层引擎也不同（JavaScriptCore vs V8）。命令层面几乎能一一对应，学习成本低；真正的成本是"不确定性成本"：兼容问题不好判断是谁的锅、生态和 CI/Docker 支持、团队环境要统一。判断依据：项目性质、团队熟悉度、运行环境、出问题谁填坑。

### Q6：根目录 package.json 的 workspaces / packageManager / scripts 各起什么作用？
- `workspaces`：告诉 Bun 这个仓库里有哪些子项目。缺了会提示 "No packages"
- `packageManager`：Turbo 靠它识别包管理器和 lockfile，缺了可能直接报错
- `scripts`：全仓库统一命令入口，只需记根目录命令。缺了会报 `Script not found`

### Q7：turbo.json 里 `dependsOn: ["^build"]` 的 `^` 是什么意思？
`^` 指"我依赖的那些项目"。意思是构建我之前先构建我依赖的项目。例如 chat-web 依赖 contracts，Turbo 会自动先构建 contracts。不加 `^` 则指本项目自己的任务。

### Q8：dev 任务为什么设置 cache: false 和 persistent: true？
dev 是开发服务器，一直运行、代码随时在改，没有"跑完的结果"可以复用，开缓存可能导致回放旧输出而不是真正启动服务；`persistent: true` 告诉 Turbo 这个任务不会自己结束，别傻等它跑完。

### Q9：什么是幽灵依赖？isolated installs 怎么解决？
普通安装会把"依赖的依赖"提升到最外层 node_modules，于是没在 package.json 里声明的包也能被 import，本地能跑，换环境重装或上游包不再依赖它时突然报错。isolated 模式下每个子项目只能用到自己声明过的包，没声明立刻报错，问题提前暴露。

### Q10：`"@autix/contracts": "workspace:*"` 是什么意思？
`workspace:` 表示用本仓库里的这个包，不去 registry 下载；`*` 表示不限版本。安装时会在 node_modules 建链接指向 packages/contracts，改完共享包立刻生效，不需要发版。

### Q11：next.config.ts 里 transpilePackages 为什么必须加？
共享包的 exports 指向的是 `.ts` 源码，而 Next 默认不编译 node_modules 里的包（假设都是编译好的 JS）。加上这一行告诉 Next 这个包是源码、要一起编译，否则前端引用会报错。

### Q12：outputFileTracingRoot 为什么要设成仓库根目录？
standalone 构建会追踪"运行需要哪些文件"。前端在 clients/chat-web，共享包在 packages/contracts，在它外面。不设置就只在前端目录里找，打包会漏掉共享包——典型表现是开发能跑、构建缺文件。

### Q13：为什么前端环境变量必须以 NEXT_PUBLIC_ 开头？
页面代码运行在浏览器里，读不到服务器环境变量。Next 打包时只把 `NEXT_PUBLIC_` 开头的变量值内联进浏览器 JS。这是安全设计：数据库密码、模型 Key 等不会被误暴露。注意值是构建时写入的，build 之后改环境变量不会生效。

### Q14：/health 和 /hello 分别给谁用？
`/health` 给程序用（Compose 健康检查、监控），只回答"服务活着没"，返回越简单越稳定；`/hello` 给前端和人用，返回值带共享包的 APP_NAME，一次请求同时验证接口通、共享包可用、前端能消费。

### Q15：为什么 curl 能访问接口，浏览器页面却报跨域错误？
跨域是**浏览器**强制执行的安全策略（协议+域名+端口任一不同即跨域），服务端并不会拒绝请求。curl 不是浏览器，不执行这套策略。所以排查时不能只用 curl 验证。

### Q16：解决跨域的两种方案？
- 方案 A：后端 `enableCors` 声明允许的来源。只放行自己的前端而非 `*`，避免任何站点都能调用（尤其接口会花钱或带登录态时）
- 方案 B：Next `rewrites` 把 `/api/*` 转发到后端。浏览器只发同源请求，服务器之间转发不受跨域限制，还能隐藏后端地址

### Q17：build.context 为什么写仓库根目录？
Docker 构建只能 COPY 上下文目录内的文件。context 设成 infra/compose 就拿不到 packages/contracts，共享包进不了镜像。dockerfile 路径是相对 context 写的。

### Q18：healthcheck + depends_on condition: service_healthy 解决什么？
只写 depends_on 仅保证容器先启动，不保证里面的服务已就绪；加上 condition 会等健康检查通过再启动依赖方，避免前端启动后接口还连不上。

### Q19：容器里 wait-on tcp:4001 为什么等不到？
容器里的 localhost 指容器自己，后端在另一个容器，应使用 Compose 服务名（如 `chat:4001`）。但浏览器里的 API 地址仍用 `localhost:4001`，因为浏览器跑在宿主机上，通过端口映射访问。

### Q20：ESM 项目照抄不带 .js 的 import 会怎样？
报 `Cannot find module`。`"type": "module"` 下 ESM 要求相对路径 import 写完整文件名，编译后是 .js，所以源码里就要写 `.js`。CommonJS 会自动补后缀，所以旧版课程代码不用写。原则：以脚手架生成的代码风格为准。

### Q21：给 AI 代理写工程搭建 Prompt，最值钱的是什么？
不是描述"我想要什么"，而是把**边界、顺序、验收**写清楚：明确目录/命名/端口/脚本入口，拆成有检查点的步骤，规定交付格式和报错时的处理方式。这样模型偶尔跑偏也能被快速拉回。
