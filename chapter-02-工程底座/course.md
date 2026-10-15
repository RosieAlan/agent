# 第二章：搭建智能体的工程底座

第一章解决了"怎么把模型用起来"（模型调用、Prompt 设计、结构化输出）。这一章问题从"能力本身"转向"能力如何落地为可持续演进的系统"：这些能力应该放在前端还是后端？前后端如何分工与对齐接口？共享的类型、schema、DTO 应该沉淀在哪里？当后续逐步加入工具调用、RAG、MCP、多智能体编排时，今天的工程结构还能不能顺滑扩展、而不是推倒重来？

本章用 Bun workspaces 搭建一个可扩展的 monorepo，把工程明确拆成三层：
- `clients/`：客户端应用
- `services/`：服务进程
- `packages/`：共享子包

在这个体系里，**Bun** 负责工作区和依赖管理，**Turbo** 负责任务编排与缓存，**Docker Compose** 负责多服务启动与环境编排，**YAML** 负责应用配置和环境覆盖。

---

## 2.1 为什么从一开始就选 monorepo

**跨层接口约定会一起变，多仓库同步成本很高**
类型、schema、DTO、工具参数、前端消费的数据结构，往往会同时出现在客户端、服务端和共享层。若拆成多个仓库，一次字段调整意味着：要在多个仓库分别改代码、分别发版与升级依赖、处理版本不一致带来的兼容窗口。而 monorepo 里，这类改动可以在一次提交中完成，接口约定也更容易保持一致。

**共享代码与共享定义在同一仓库里更"自然"**
只要系统存在共享包（shared、utils、sdk、prompts），多仓库就会引入一条额外链路：发布与安装。它会把"共享"变成一种持续成本：共享包升级滞后、同一份能力在不同仓库重复实现、为兼容旧版本被迫维护更多分支和适配代码。monorepo 把共享包留在仓库内部，以 workspace 方式直连，减少重复与漂移。

**系统一旦扩张，多仓库往往需要二次迁移**
现在可能只有 web + api，一旦增加 worker、agent-runtime、prompt 包、sdk 包，多仓库容易出现仓库数量持续膨胀、依赖关系越来越像网、跨仓库改动变成常态。monorepo 的价值不只是"现在好管理"，更重要的是它能承接后续扩展，不需要在系统变复杂之后再做仓库级迁移。

> 选择 monorepo，是为了更低成本地实现三件事：共享代码更自然、跨项目改动更原子化、依赖与接口定义更一致。
>
> monorepo 的代价也客观存在：仓库规则、边界约束与任务编排会变得更重要。这不是缺点，而是"把复杂度提前显式化"。

---

## 2.2 为什么选 Bun / Next / Nest / Turbo / Compose

选择标准：以 TypeScript + monorepo 为前提，优先保证"能稳定跑起来"而不是追求最潮的栈，给后续智能体能力扩展（模型调用、工具调用、RAG、运行时、多服务）留足空间。

**Bun：用一套工具解决 runtime + 包管理 + workspaces**
相比 Node + npm/pnpm/yarn 的组合，Bun 把"跑 TS/JS、装依赖、管理 workspaces、执行脚本"收敛成一条链路：环境与安装链路更短，出问题的环节更少；workspaces + catalog 更容易把依赖版本收敛；isolated installs 更适合在 monorepo 里减少隐性依赖。这不是说 Bun 一定强过所有包管理器，而是它在"工程底座阶段"更省心。
> 如果是公司级、追求稳定的项目，用传统的 pnpm 或 yarn 会更稳妥（经过更充分验证）；如果是个人项目或创新探索，按 Bun 走、一起踩坑也未尝不可。

**Next.js：让客户端交付与工程化保持简单、可靠**
React 生态成熟，页面与路由能力完整；monorepo 下可直接消费共享包（`transpilePackages`）；从开发到部署链路闭环。

**NestJS：用模块化容器承接服务端的复杂度增长**
智能体系统的复杂度大概率在服务端累积。Nest 的模块化 + 依赖注入适合承载会持续增长的能力（模型调用、工具、RAG、运行时）；Controller / Service 分层清晰，可测试、可维护。相比"轻框架/纯脚本"，Nest 的优势在于：复杂度上来时不需要推倒重来。

**Turbo：用任务图与缓存，让 monorepo 的运行成本可控**
很多 monorepo 的痛点不是代码组织，而是任务执行：build、typecheck、test、lint 一多就会拖慢。Turbo 解决任务之间的依赖关系（任务图）、增量执行（只跑受影响部分）、缓存复用（本地与 CI 都能受益）。

**Docker Compose：把多个服务当成一个系统来启动与联调**
用一套 YAML 定义多服务的启动、端口、依赖顺序、环境变量；多文件覆盖（dev/prod）让环境切换更可控；对本地联调与单机交付非常友好。

> 一句话总结：这套组合的目标不是"最强栈"，而是用最少的工具，把仓库管理、客户端交付、服务端承载、任务执行、多服务运行这五件事一次性补齐，并且在后续引入智能体能力时不需要频繁更换底层方案。

---

## 2.3 总览：会搭一个"能跑起来"的最小工程

- `packages/contracts`：共享包（类型 / 校验规则 / 常量）
- `services/chat`：Nest Chat 服务（提供 `/health` 与 `/hello`）
- `clients/chat-web`：Next Web（页面渲染 + 调用 Chat 服务）
- `infra/compose`：Docker Compose（一次命令启动 chat-web + chat）

设计意图：先把工程骨架和联通方式跑通。后续无论接不接模型、接什么工具、引入什么运行时，都可以在这个骨架上逐步加能力，而不是一开始就被"选型细节"困住。

**✅ 最终验收标准**：浏览器打开 `http://localhost:3002` 能看到页面展示的 `APP_NAME`；点击按钮后页面能调用 Chat 服务并显示返回字符串；用 Compose 一条命令能同时启动 chat-web 与 chat。

---

## 2.4 根目录与共享包：先把"仓库底座"跑通

### 2.4.0 安装 Bun

```bash
curl -fsSL https://bun.com/install | bash
bun --version
```

### 2.4.1 建立目录骨架

```bash
mkdir llm && cd llm
mkdir -p clients services packages/contracts/src infra/compose
```

```
llm/
├─ clients/
├─ services/
├─ packages/
│  └─ contracts/
│     └─ src/
├─ infra/
│  └─ compose/
├─ package.json
├─ turbo.json
├─ bunfig.toml
└─ tsconfig.base.json
```

### 2.4.2 根目录 package.json（workspaces + 顶层脚本 + 版本收敛）

根目录 `package.json` 是 monorepo 的控制面板：`workspaces.packages` 决定哪些目录被当作工作区；`scripts` 提供全仓统一入口；`packageManager` 让 Turbo 能稳定识别包管理器，据此解析 lockfile、package graph 与缓存行为。

```json
{
  "name": "root",
  "private": true,
  "workspaces": ["clients/*", "services/*", "packages/*"],
  "packageManager": "bun@1.3.11",
  "scripts": {
    "clean:ports": "for port in 3002 4001; do lsof -ti :$port | xargs kill -9 2>/dev/null; done; echo 'Ports cleaned'",
    "dev": "bun run clean:ports && turbo run dev --parallel --filter=@autix/chat --filter=@autix/chat-web",
    "dev:chat-web": "turbo run dev --filter=@autix/chat-web",
    "dev:chat": "turbo run dev --filter=@autix/chat",
    "build": "turbo run build",
    "typecheck": "turbo run typecheck",
    "lint": "turbo run lint"
  },
  "devDependencies": {
    "turbo": "^2.8.20",
    "wait-on": "^9.0.5"
  }
}
```

> ⚠️ **关键细节**：`packageManager` 是 Turbo 识别包管理器的关键字段。缺少它，Turbo 会进行 package manager check，可能导致 build 失败。更推荐补齐 `packageManager`，而不是在 `turbo.json` 里打开 `dangerouslyDisablePackageManagerCheck`。

### 2.4.3 bunfig.toml（isolated installs）

`isolated installs` 会让每个工作区的依赖边界更清晰，能更早暴露"隐式依赖"和"幽灵依赖"（phantom dependency）问题，避免仓库变大后才发现安装结果不可复现。

```toml
[install]
linker = "isolated"
```

> ⚠️ isolated installs 会更严格，会更早暴露缺失依赖或隐式依赖的问题。对新仓库来说这是优点。

### 2.4.4 turbo.json（任务图 + 缓存边界）

Turbo 需要用 `tasks`/`dependsOn`/`outputs` 把 build、dev、typecheck 等任务组织成"任务图"，并划定缓存边界，让后续工作区变多时能增量执行、复用缓存。

```json
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**", ".next/**"]
    },
    "dev": {
      "dependsOn": ["^build"],
      "cache": false,
      "persistent": true
    },
    "typecheck": {
      "dependsOn": ["^typecheck"]
    }
  }
}
```

### 2.4.5 tsconfig.base.json（统一 TS 基线 + contracts 路径别名）

把 TypeScript 的严格模式、模块解析策略、共享包的路径别名统一到根目录，避免 web/chat/共享包各自为政。后续加新包时只需要 `extends` 这份基线。

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022"],
    "paths": {
      "@autix/contracts": ["./packages/contracts/src/index.ts"],
      "@autix/contracts/*": ["./packages/contracts/src/*"]
    }
  }
}
```

### 2.4.6 初始化 packages/contracts（本例的"共享包"）

先建一个最小共享包，验证"跨项目共享"这件事确实能跑通。后面类型、校验规则、DTO 等会逐步往这里沉淀。

**packages/contracts/package.json**（让 Bun workspaces 把这个目录识别为可依赖的包，并通过 `exports`/`types` 暴露共享入口）：

```json
{
  "name": "@autix/contracts",
  "version": "0.0.0",
  "exports": "./src/index.ts",
  "types": "./src/index.ts",
  "dependencies": {
    "zod": "^3.23.8"
  }
}
```

**packages/contracts/tsconfig.json**（共享包需要自己的编译边界，让 web/chat 在编译期拿到类型信息）：

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src"]
}
```

**packages/contracts/src/index.ts**（先放一个常量最容易验证"共享包是否被正确引用"——只要 web 和 chat 都能读到同一个 `APP_NAME`，就说明 workspace 依赖、构建链路和路径解析是通的）：

```typescript
export const APP_NAME = "llm";
```

### 2.4.7 安装依赖（全仓一次安装）

```bash
bun install
bun run build
```

**✅ 验收标准**：根目录执行 `bun install` 不报错；`bun run build` 时后续的 `@autix/chat-web` / `@autix/chat` 能解析到本地 workspace 包 `@autix/contracts`。

---

## 2.5 客户端：初始化 Next 并使用共享包

目标：初始化 `clients/chat-web`，让 Next 项目在 monorepo 里以 workspace 方式被管理；让 Web 端可以直接引用 `@autix/contracts`，前后端共享同一份常量/类型定义。一旦前端能在编译期直接依赖共享定义，后面无论 API 调用、表单校验、DTO 还是工具参数，都可以持续复用同一份定义，避免前后端各自复制粘贴、越走越分叉。

### 2.5.1 初始化 clients/chat-web

```bash
bun create next-app clients/chat-web --yes
```

把 `clients/chat-web/package.json` 调整为（关键点：包名统一、脚本使用 Bun、依赖通过 `workspace:*` 直连共享包）：

```json
{
  "name": "@autix/chat-web",
  "version": "0.0.0",
  "private": true,
  "scripts": {
    "dev": "wait-on tcp:4001 && next dev --port 3002",
    "build": "next build",
    "start": "next start --port 3002",
    "typecheck": "tsc --noEmit",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "@autix/contracts": "workspace:*",
    "next": "16.2.3",
    "react": "19.2.4",
    "react-dom": "19.2.4"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.0.0",
    "@types/node": "^22",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.7.0",
    "wait-on": "^9.0.5"
  }
}
```

### 2.5.2 tsconfig 继承根目录基线

TypeScript 的"基线规则"统一收敛在根目录，具体项目只做最小差异化配置。避免后面新增 client 包时每个项目一套 TS 口径的漂移。

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts", ".next/dev/types/**/*.ts", "**/*.mts"],
  "exclude": ["node_modules"]
}
```

### 2.5.3 next.config.ts（monorepo 必配项）

在 monorepo 里，Next 需要显式声明"哪些 workspace 包要参与转译"以及"standalone tracing 的根目录"。否则常见症状是：开发环境能跑，但构建产物缺共享包文件、或类型解析不完整。

```typescript
import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@autix/contracts"],
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname, "../../"),
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:4001",
  }
};

export default nextConfig;
```

> ⚠️ **关键细节**：必须设置 `outputFileTracingRoot`，否则在 monorepo 下做 standalone 构建时，仓库外层的共享包可能不会被正确纳入 tracing 范围。

### 2.5.4 最小页面：显示 APP_NAME

用最小页面验证两件事：`@autix/contracts` 的依赖解析是通的（能 import）；共享常量在 Web 端能被正确打包并渲染（能展示）。

```tsx
"use client";
import { useState } from "react";
import { APP_NAME } from "@autix/contracts";

export default function Home() {
  const [result, setResult] = useState<string>("");

  async function callApi() {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/hello`);
    const data = await res.json();
    setResult(data.message);
  }

  return (
    <main style={{ padding: 24 }}>
      <h1>{APP_NAME}</h1>
      <button onClick={callApi}>调用 API</button>
      <pre style={{ marginTop: 16 }}>{result}</pre>
    </main>
  );
}
```

启动：`bun install`（新增了本地的 `@autix/contracts` 依赖，需要重新安装以更新 workspace 引用）→ `bun run dev`。

> 当前分支里 `@autix/chat-web` 的 `dev` 脚本会等待 4001 端口可用，因此推荐用根命令 `bun run dev` 同时启动 `@autix/chat` 与 `@autix/chat-web`。如果只启动 Web，需先在另一个终端运行 `bun run dev:chat`，再运行 `bun run dev:chat-web`。

**✅ 验收标准**：打开 `http://localhost:3002`，页面显示 `llm`；下一节的 `@autix/chat` 启动后，点击"调用 API"能显示 `/hello` 返回内容。

---

## 2.6 服务端：初始化 Nest 并提供最小 API

目标：初始化 `services/chat`，让 Nest 服务以 workspace 方式进入 monorepo 任务图；提供两个最小接口 `GET /health` 与 `GET /hello`；在 `/hello` 里引用 `@autix/contracts`，验证"共享包在服务端同样可用"。

这里先不接模型，是刻意的：先把"服务能跑、路由能通、共享包能引用、前端能调到后端"这条最小链路跑通，后面接模型、做工具调用、引入运行时都是在这条链路上加能力，而不是一开始就把问题复杂化。

### 2.6.1 初始化 services/chat

```bash
bunx @nestjs/cli new services/chat
```

把 `services/chat/package.json` 调整为（关键点：包名统一、脚本与运行方式明确、通过 `workspace:*` 引用 `@autix/contracts`）：

```json
{
  "name": "@autix/chat",
  "version": "0.0.0",
  "private": true,
  "scripts": {
    "dev": "nest start --watch",
    "build": "rm -rf dist tsconfig.tsbuildinfo && nest build",
    "start": "bun run dist/main.js",
    "typecheck": "tsc --noEmit",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "@autix/contracts": "workspace:*",
    "@nestjs/common": "^11.0.0",
    "@nestjs/core": "^11.0.0",
    "@nestjs/platform-express": "^11.0.0",
    "reflect-metadata": "^0.2.0",
    "rxjs": "^7.8.0"
  },
  "devDependencies": {
    "@nestjs/cli": "^11.0.0",
    "@nestjs/schematics": "^11.0.0",
    "@types/express": "^5.0.0",
    "@types/node": "^22.0.0",
    "typescript": "^5.7.0"
  }
}
```

### 2.6.2 注册两个最小路由：health 与 hello

- `/health`：为 Compose/健康检查/监控提供一个稳定的探针
- `/hello`：用于验证"共享包 + API 返回 + 前端消费"的最小闭环

这里的返回值刻意保持简单，目的只是让链路可验证、可定位问题。

```typescript
// services/chat/src/app.controller.ts
import { Controller, Get } from '@nestjs/common';
import { AppService } from './app.service';

@Controller()
export class AppController {
  constructor(private readonly appService: AppService) {}

  @Get('health')
  getHealth() {
    return this.appService.getHealth();
  }

  @Get('hello')
  getHello() {
    return this.appService.getHello();
  }
}
```

```typescript
// services/chat/src/app.service.ts
import { Injectable } from "@nestjs/common";
import { APP_NAME } from "@autix/contracts";

@Injectable()
export class AppService {
  getHello(): { message: string } {
    return { message: `Hello from Chat, shared APP_NAME=${APP_NAME}` };
  }

  getHealth(): { ok: boolean } {
    return { ok: true };
  }
}
```

### 2.6.3 修改端口到 4001（Nest 默认是 3000）

NestJS 默认监听 3000，为了和 Web 的 3002 区分，Chat 服务统一使用 4001。在 `main.ts` 显式指定端口，并放行本地 Web 的跨域请求：

```typescript
// services/chat/src/main.ts
import 'reflect-metadata';
import { NestFactory } from "@nestjs/core";
import { AppModule } from "./app.module";

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors({ origin: process.env.CORS_ORIGIN || "http://localhost:3002" });
  const port = process.env.PORT ?? 4001;
  await app.listen(port);
  console.log(`Chat service running on http://localhost:${port}`);
}
bootstrap();
```

启动：`bun i`（同理，新增了 workspace 依赖后需要安装）→ `bun run dev:chat`。

**✅ 验收标准**：`curl http://localhost:4001/hello` 返回 `Hello from Chat...`；`curl http://localhost:4001/health` 返回 `{ "ok": true }`。

---

## 2.7 前后端联通：Web 调用 Chat 服务并展示结果

目标：在 Web 端通过 `fetch` 请求 Chat 服务的 `GET /hello`，把返回的 `message` 展示在页面中，完成一次"可见的端到端验证"。这一节把"工程底座"从静态结构变成了可验证的系统——能看到请求发出、响应回来、页面更新。后面无论引入表单、鉴权、模型调用还是多服务，都建议沿用同样的思路逐层验收。

### 2.7.1 在 Web 页面加一个按钮调用 API

（代码同 2.5.4）用按钮触发请求并渲染结果，方便在浏览器里直接观察链路是否工作。

> ⚠️ **关键细节**：客户端必须通过 `NEXT_PUBLIC_` 前缀拿到 API 地址——只有这个前缀的环境变量才会在浏览器端可用。

### 2.7.2 在 Next 里注入 NEXT_PUBLIC_API_BASE_URL（最小版）

先用 `next.config.ts` 直接注入默认值把链路跑通，后续在 2.8（Compose + YAML）升级为"配置文件驱动"。

### 2.7.3 处理跨域（两种最小方案）

**方案 A：在 NestJS 里开启 CORS（最简单）**

```typescript
app.enableCors({
  origin: process.env.CORS_ORIGIN || "http://localhost:3002",
  credentials: true,
});
```

**方案 B：在 Next.js 里做反向代理（避免浏览器跨域）**

把浏览器请求打到同域（`/api/*`），再由 Next 转发到后端：

```typescript
// next.config.ts
async rewrites() {
  return [
    { source: "/api/:path*", destination: "http://localhost:4001/:path*" },
  ];
},
```

前端请求改成 `fetch("/api/hello")`，浏览器看到的是同域请求（localhost:3002），不会触发 CORS。

### 2.7.4 运行整条链路

根目录执行 `bun run dev`。

**✅ 验收标准**：打开 `http://localhost:3002`，点击"调用 API"按钮，页面显示 API 返回的 `message`。

---

## 2.8 用 Docker Compose 把 Web + Chat 当成一个系统启动

目标：写出 `compose.yaml` + `compose.dev.yaml`，一条命令启动 chat-web + chat，用 `healthcheck` + `depends_on` 保证启动顺序可控。

### 2.8.1 Compose 基础文件

```yaml
# infra/compose/compose.yaml
services:
  chat:
    build:
      context: ../..
      dockerfile: infra/compose/Dockerfile.chat
    ports:
      - "4001:4001"
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:4001/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  chat-web:
    build:
      context: ../..
      dockerfile: infra/compose/Dockerfile.web
    ports:
      - "3002:3002"
    depends_on:
      chat:
        condition: service_healthy
```

### 2.8.2 开发覆盖文件（挂载源码）

```yaml
# infra/compose/compose.dev.yaml
services:
  chat:
    command: bun run dev
    volumes:
      - ../../services/chat/src:/app/services/chat/src
      - ../../packages/contracts:/app/packages/contracts
  chat-web:
    command: bun run dev
    volumes:
      - ../../clients/chat-web:/app/clients/chat-web
      - ../../packages/contracts:/app/packages/contracts
```

### 2.8.3 Dockerfile.chat 与 Dockerfile.web

compose.yaml 中引用的两个 Dockerfile 都放在 `infra/compose/` 下，但构建上下文是仓库根目录（`context: ../..`），以便在构建时能访问到 `packages/contracts` 等共享包。共同思路：以仓库根为构建上下文完整复制 monorepo；多阶段构建（deps 装依赖，build 编译，最终阶段只保留运行所需文件）；生产镜像尽量精简。

```dockerfile
# Dockerfile.chat
FROM oven/bun:1-alpine AS base
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .
RUN bun run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=base /app/dist ./dist
EXPOSE 4001
CMD ["bun", "run", "dist/main.js"]
```

```dockerfile
# Dockerfile.web
# Next.js 已开启 output: "standalone" 与 outputFileTracingRoot，
# 最终镜像只需拷贝 .next/standalone 与 .next/static，不需要 node_modules 全量
FROM oven/bun:1-alpine AS base
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .
RUN bun run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=base /app/.next/standalone ./
COPY --from=base /app/.next/static ./
COPY --from=base /app/public ./public
EXPOSE 3002
CMD ["node", "server.js"]
```

> 原文注：dockerfile 也可以参考生产版本，目前只是 demo，暂时不必须运行起来。

### 2.8.4 启动命令

```bash
docker compose -f infra/compose/compose.yaml -f infra/compose/compose.dev.yaml up --build
```

**✅ 验收标准**：`http://localhost:3002` 正常打开；点击按钮后依然能拿到 API 返回。

---

## 2.9 用 Claude CLI 把流程跑一遍

2.4–2.8 是手动把工程一步步搭出来的：先跑通仓库底座，再分别跑通 Web、Chat 服务、联通、Compose。这样做的价值在于：你已经知道每一步在解决什么问题、文件应该放在哪里、哪些配置是"非做不可"。

2.9 要做一次递进：**2.4–2.8 解决的是"我会手动搭出来"，2.9 解决的是"我能把同样的步骤交给代理重复执行，而且结果不跑偏"**。

### 2.9.1 角色分工

- **Claude CLI**：负责在本地仓库里改文件、执行命令、修报错
- **Prompt**：负责把"要搭成什么样"写清楚（结构、约束、验收标准）
- **Superpowers skills（可选）**：当希望把流程拆成 plan + tasks 并复用时更顺手

> 工具不决定质量，说明是否清楚才决定质量。

### 2.9.2 为什么要写 Prompt

只说"帮我搭一个 monorepo + Next + Nest"，大概率出现：目录结构与命名不稳定、dev/build 脚本入口不统一、Next 在 monorepo 下缺关键配置（能 dev 不能 build）、Compose/端口/健康检查不一致。而 2.4–2.8 已经把"正确的做法"固定下来，这一节把它浓缩成可执行说明，让代理按同一套规则复现。

### 2.9.3 如何写一个规范且"可控"的 Prompt

所谓"可控"，不是让模型永远不出错，而是让它在出错时也能被快速纠偏。建议结构（从上到下依次收紧约束）：

1. **角色与工作方式**：指定工作身份（"你是一个会在本地仓库修改文件并执行命令的工程助手"）；强制过程化（严格按步骤执行、每步汇报变更、报错先贴完整日志再修）
2. **目标**：1-3 句话写清最终交付形态，用可验证目标替代泛目标
3. **约束**：明确目录结构、命名规范、端口、脚本入口、必须/禁止使用的工具链；明确禁止项（不改无关文件、不发散引入额外技术栈）
4. **分步计划**：拆成 4-8 步，每步包含输入前置条件、要产生的产物、本步验收方式；顺序符合依赖关系（先底座，再子项目，再联通，再编排）
5. **交付格式**：要求输出"变更清单"和"如何运行"的命令序列
6. **失败处理**：约定报错时的行为——保留报错原文、不跳步、先最小修复再继续

> 这一章的经验法则：Prompt 里最值钱的不是"描述你想要什么"，而是把"边界、顺序、验收"写清楚。只要这三件事稳定，模型就算偶尔偏航，也会被快速拉回既定轨道。

### 2.9.4 递进清单

按同样节奏组织说明（从底座到联通）：
1. 仓库底座（对应 2.4）：Bun workspaces + Turbo，根目录脚本，bunfig.toml，tsconfig.base.json
2. 共享包（对应 2.4.6）：packages/contracts 提供 APP_NAME
3. Web（对应 2.5）：clients/chat-web，必配 transpilePackages + outputFileTracingRoot
4. Chat 服务（对应 2.6）：services/chat，提供 /health、/hello，监听 4001
5. 联通（对应 2.7）：Web 调用 Chat，处理跨域
6. Compose（对应 2.8）：compose.yaml + compose.dev.yaml，healthcheck + depends_on

### 2.9.5 简化 Prompt

> 完整 Prompt 见课程原文 2.9.5 节，核心内容已在 2.9.4 的递进清单和前面各小节中体现，包含逐步的目录结构、package.json 字段、端口配置和交付要求等具体细节。

### 2.9.6 沉淀为 skills（可选）

当发现自己会反复做类似事情（加更多服务/客户端/共享包）时，更好的递进是：第一次用长 Prompt 跑通一次 → 把 Prompt 拆成多个可复用步骤（初始化底座 / 添加 Next / 添加 Nest / 添加 Compose）→ 第三次开始直接调用对应 skills，让代理按同样规则扩展工程。

---

## 2.10 本章总结：先跑通底座，再让它可复现

这一章的核心不是"选了哪些工具"，而是把一个会持续扩展的智能体工程，先搭成一个能跑、能验证、能复用的底座。三层递进：

1. **把结构搭对**（目录、边界、依赖）
2. **把链路跑通**（Web ↔ Chat 服务 ↔ 共享包 ↔ Compose）
3. **把流程固化**（写成 Prompt，让代理可重复执行）

### 2.1–2.3 的结论
- 从一开始采用 monorepo，是为了让跨层定义与跨项目改动保持一致，避免仓库数量增加后同步成本失控
- Bun / Next / Nest / Turbo / Compose 组合目标是"少而全"
- 2.4–2.8 的最小工程不是为了炫技，而是为后续引入模型、工具调用、RAG 和多服务扩展提供稳定骨架

### 2.4–2.8 跑通的最小闭环
- `packages/contracts`：前后端共享同一份常量/类型/规则，避免重复定义
- `clients/chat-web`：能读取共享包内容，并通过按钮触发请求
- `services/chat`：提供最小可验证接口（/health、/hello），并能读取共享包内容
- "联通"不是一句话：必须在浏览器里看到请求发出、响应回来、页面更新，才算真的跑通
- `infra/compose`：把多个服务当成一个系统来启动，通过 healthcheck + depends_on 把联调变成可控流程

### 2.9 学到的工程化方法
- 手动搭建的价值在于理解边界与关键配置；规则固定后，重复劳动应该交给代理
- 关键不是"让 AI 写代码"，而是把要求写清楚：目录、脚本入口、端口、Next 的 monorepo 配置、Compose 的健康检查
- 完整 Prompt 可以直接复现 2.4–2.8 的结果；开始频繁扩展工程时，再考虑把流程拆成可复用步骤

**✅ 本章的最终产物**：一套能跑起来的最小工程骨架（Web + Chat 服务 + 共享包 + Compose）；一套清晰的验收方式（每一层都有可见的验证点）；一份可复现的 Prompt（把流程从"手工"升级为"可重复执行"）。

**➡️ 下一章方向**：当底座稳定之后，模型调用、工具调用、记忆、RAG、多智能体流程都应该"按同样的方式递进"：先落在正确的层，再跑通最小闭环，再把流程固化。
