# 运营工作台

独立 Vue 3 + TypeScript 用户工作台，后端为同项目 `backend`（8020）。业务数据来自真实 API，合成演示数据在界面持续标注。

## 运行

使用 Node 22.19.0，在当前目录执行：

```powershell
npm ci
npm run dev
```

打开 `http://127.0.0.1:3020`。开发服务器将 `/api/*` 去除 `/api` 前缀后转发至 `http://127.0.0.1:8020`，`/knowledge` 保留原路径转发。

```powershell
npm run typecheck
npm run build
```

生产静态文件生成于 `dist/`，Nginx 同源代理规则与开发代理一致。知识库中的表单、上传和问答请求也沿用 `/knowledge/*`。

## 调用链

`src/main.ts` 挂载页面 → `src/App.vue` 处理用户操作 → `src/api.ts` 发送带 15 秒超时的请求 → `/api/operations/*` → Python API → 后台任务与数据库。

- 页面每 5 秒更新任务、统计、待办和通知。组件销毁清理定时器并取消请求。
- 巡检和日报提交使用 UUID 幂等编号。网络错误后保留原编号与阈值，重试请求复用它们；服务端确认接收后清除编号。
- 列表初始为空，读取失败保留上次数据与更新时间。后端 HTML、格式异常、网络错误、超时均在页内给出处理提示。
- 定时设置使用 `Asia/Shanghai`，库存查询阈值与每个定时任务阈值分别保存。
- 该工作台为本地演练入口；生产访问控制由后续上线模块接入。

## API 与版本依据

[Vue 官方快速开始](https://vuejs.org/guide/quick-start.html)；[Vite 官方入门](https://vite.dev/guide/)。2026-11-10 核对，依赖使用 npm 稳定标签解析后精确锁定，安装结果以 `package-lock.json` 为准。
