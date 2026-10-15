# 第 2.5 章：用 AI 接管工程化开发——从工程底座到能力链路

> 过渡章节。本章分支：`feat/user-system`

第二章把智能体工程的底座搭了起来：monorepo、Web、API、共享包、Compose，以及一套可被 AI 代理复现的初始化流程。第三章会正式进入 LangChain。

两章之间有一个容易被忽略的问题：**工程底座已经有了，AI 到底应该怎样参与后续开发，才不会把项目带偏？**

本章不重复第二章的搭建细节，也不提前展开 LangChain API，而是把 **Superpowers**、**ui-ux-pro-max** 和一个 **RBAC 用户权限系统**放在一起，看 AI 编程怎样从"能生成代码"走向"能按工程节奏交付"。

案例：**单租户后台管理系统里的 RBAC 用户权限系统**。它会碰到后端建模、接口、鉴权、前端页面、联调与交付，但不涉及 ABAC、行级权限、组织继承、多租户隔离这些更重的主题。

> 作者说明：示例项目虽然按下文流程推进，但过程中依然处理了不少 bug，受 AI 幻觉影响部分分支也出现过偏差。本章强调的不是"AI 一次生成完整系统"，而是**怎样让 AI 在可控流程里持续推进真实项目**。

---

## 一、Superpowers 与 ui-ux-pro-max 的定位

### 1.1 Superpowers：面向工程流程的 AI 开发工作流

AI 编程让人又爱又烦，本质上不是模型不会写代码，而是它**太容易过早进入实现阶段**：刚抛出需求就开始生成文件，话还没说完就默认做了三层扩展。

Superpowers 的核心思路，是把"先写再说"改造成更接近工程实践的工作流。它不是单一 Skill，而是一套围绕软件开发流程组织的技能系统：从 brainstorm、plan，到执行、TDD、review、收尾，让代理在每个阶段做该做的事。

### 1.2 ui-ux-pro-max：面向前端产出的设计增强能力

AI 生成的前端页面常常"布局有、按钮有、表格有"，但停留在"摆上去"的层面，缺少配色节奏、版式层级、字号体系、交互一致性这些设计判断。

ui-ux-pro-max 是为 AI coding assistant 提供 design intelligence 的 Skill。**它不是 UI 组件库，也不是设计工具，而是给模型补设计经验的知识层。**

### 1.3 两者的互补关系

- **Superpowers**：解决"开发过程是否可控"
- **ui-ux-pro-max**：解决"前端结果是否足够成熟"

### 1.4 什么时候用哪个

**Superpowers 适合：**
- 中大型功能开发，一次对话完成不了
- 同时涉及后端建模、接口、前端、测试的多模块联动
- 需要跨 session 持续推进，上下文断了也能恢复
- 需要可审计、可复盘的交付结果

**Superpowers 不容易起效：** 修小 bug、一次性脚本、快速验证原型、需求本身还不收敛的创意型工作。

**ui-ux-pro-max 适合：** 页面目标和组件库已确定，需要更统一成熟的设计产出；技术栈较主流（React、Next.js、Tailwind 等）。

**ui-ux-pro-max 不适合：** 还在探索风格方向；仓库本身设计不统一、组件混乱。

> 💡 最常见的用法：**先用 Superpowers 把任务拆清楚、推到后端骨架就位，再用 ui-ux-pro-max 进入前端阶段**。前者管流程，后者管界面。

---

## 二、安装与基础验证

不同平台安装方式不一样。Claude Code、Cursor 这类带插件市场的环境较直接；Codex、OpenCode 等需要走手动安装说明。

### 2.1 Superpowers

```bash
# 官方 Marketplace
/plugin install superpowers@claude-plugins-official

# 或通过 Superpowers Marketplace
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

### 2.2 ui-ux-pro-max

**先决条件：Python 3.x**（它的搜索脚本依赖 Python）。很多"装了但不好使"的问题，最后都不是 Skill 本身的问题，而是本地依赖没满足。

```bash
python3 --version
```

```bash
/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill
/plugin install ui-ux-pro-max@ui-ux-pro-max-skill
```

---

## 三、官方工作流概览

Superpowers 的基本工作流：

1. `brainstorming`
2. `using-git-worktrees`
3. `writing-plans`
4. `subagent-driven-development` 或 `executing-plans`
5. `test-driven-development`
6. `requesting-code-review` / review 相关环节
7. `finishing-a-development-branch`

### 3.1 需求澄清（brainstorming）

不是"礼貌地追问几句"，而是**把模糊需求转成能继续往下推的设计起点**。最关键的产物不是聊天记录，而是后续会被固化下来的设计判断。

### 3.2 方案收敛与计划拆分（writing-plans）

把任务拆成一组**可以逐步完成、逐步验收**的动作。官方一直强调 plan 粒度要小，就是为了让长任务不会因为上下文膨胀而失控。

### 3.3 执行阶段的约束机制

对应 `executing-plans`、`subagent-driven-development`、`test-driven-development`。让执行阶段继续受测试、review 和阶段性检查的约束，而不是有了计划也照样一口气往前冲。

### 3.4 收尾与交付（finishing-a-development-branch）

很多 AI 生成代码的问题不在生成时，而在**收尾时**：没确认测试结果、没做回归、也没说明当前分支该如何处置。

### 3.5 ui-ux-pro-max 的工作方式

提出 UI/UX 相关任务时 Skill 自动激活，识别任务类型，检索对应的风格、配色、字体、布局建议，再提供给模型。**它更像"设计顾问"，而不是"页面生成器"。**

---

## 四、为什么选 RBAC 做案例

RBAC 天然有几层结构：
- 后端要建模用户、角色、权限
- 接口层要做 Guard 和装饰器
- 前端要做登录、列表、权限分配、菜单控制
- 交付阶段要处理联调、初始化数据、容器化启动

正好能把 Superpowers 的长任务工作流和 ui-ux-pro-max 的前端辅助放进同一个案例观察。

> 📌 范围边界：单租户后台管理系统里的 RBAC，**不涉及** ABAC、数据行级权限、组织/部门继承、多租户隔离。

---

## 五、在 RBAC 项目中的使用方式

### 5.1 需求边界澄清

权限系统最容易出问题的不是 CRUD，而是**边界不清时默认做了太多假设**。第一步不是写代码，而是让 AI 先把问题问完整。

```
/superpowers:brainstorm

我要做一个后台管理系统的 RBAC 权限模块。
后端使用 NestJS + Prisma + PostgreSQL，
前端使用 Next.js 16 + Tailwind 4 + HeroUI。

请不要直接写代码，先帮我把边界条件问清楚，包括：
- 权限粒度到页面、按钮还是接口
- 是否需要 super_admin 绕过机制
- refreshToken 是否落库
- 是否需要审计日志
- 是否涉及组织 / 部门 / 租户维度
```

意义：你以为要的是"后台权限控制"，模型理解成"完整企业权限平台"；你只想做按钮级控制，它顺手加上租户维度和审计模型。超出范围的内容局部不一定错，但**大概率不是你当下真正需要的**。

### 5.2 Spec 设计说明

问题问得差不多后，让 AI 把核心决策收敛成一份设计说明。关键是有没有把这几件事**说死**：

- 后端模块怎么拆
- 权限命名采用什么规范
- 前端如何接入权限判断
- **哪些内容这次明确不做**

如果这些不先落下来，后面 Plan 拆得再细，也只是把一堆摇摆中的决定拆得更碎。

### 5.3 Plan 拆分原则

不要用"实现用户模块"这种粗粒度任务名。**一步里包含的决策越多，执行时越容易发散。**

```
/superpowers:writing-plans

基于刚才对齐的 RBAC 权限系统需求，生成完整实施计划。

要求：
- 后端和前端分开规划
- 每个步骤要有明确的交付物和验收标准
- 数据库 Schema 设计作为独立步骤
- 鉴权模块和业务模块分开
- 前端页面按功能模块拆分
```

一份可执行 Plan 的结构示例：

```markdown
### Phase 1：工程底座
- [ ] 1.1 初始化 monorepo（services/user-system + clients/admin-web + packages/database）
- [ ] 1.2 配置 Prisma + PostgreSQL
- [ ] 1.3 设计并迁移数据库 Schema

### Phase 2：后端核心
- [ ] 2.1 Auth 模块（登录/刷新 Token/当前系统切换）
- [ ] 2.2 Users 模块（CRUD + 状态管理）
- [ ] 2.3 Roles 模块
- [ ] 2.4 Systems / Menus / Permissions 模块
- [ ] 2.5 JwtAuthGuard + PermissionsGuard
- [ ] 2.6 @Permissions() 装饰器

### Phase 3：前端核心
- [ ] 3.1 初始化 Next.js 16 + Tailwind 4 + HeroUI
- [ ] 3.2 登录页
- [ ] 3.3 布局和侧边栏（权限驱动菜单）
- [ ] 3.4 用户、角色、权限配置中心和个人信息页

### Phase 4：集成与收尾
- [ ] 4.1 前后端联调
- [ ] 4.2 本地启动脚本与环境变量整理
- [ ] 4.3 初始化管理员账号与默认权限
```

> **Plan 不是项目目录，而是执行顺序。** 进入下一阶段前，务必确认当前阶段验收已通过、git commit 已提交。

### 5.4 后端实现阶段

```
/superpowers:executing-plan

执行 PLAN.md 中 Phase 1 和 Phase 2 的所有步骤。
每个步骤执行完后，输出对应的验收 curl 命令。
```

重点不是让 AI 一口气生成所有代码，而是**按计划逐步推进，每一步留下可验证的结果**。

项目约定：用户系统服务 `@autix/user-system` 监听 **4002**，通过 `setGlobalPrefix('api')` 统一加 `/api` 前缀；登录用**用户名**而非邮箱；种子账号见 `packages/database/prisma/seed.ts`（超管 `admin` / `Admin@123456`）。

后端验收清单：

```bash
# 登录获取 Token
curl -X POST http://localhost:4002/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123456"}'

# 携带 Token 获取用户信息，应返回 200
curl http://localhost:4002/api/auth/profile \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# 无权限 Token 删除用户，应返回 403（不是 401）
curl -X DELETE http://localhost:4002/api/users/<userId> \
  -H "Authorization: Bearer <limitedToken>"

# super_admin 应能访问所有接口
curl http://localhost:4002/api/users \
  -H "Authorization: Bearer <superAdminToken>"
```

验收标准（具体因实现而异，可交由 AI 生成）：
- ✅ 登录成功返回 accessToken / refreshToken；调用 `/auth/profile` 获取当前用户、菜单和权限列表
- ✅ 有权限接口返回 200
- ✅ 无权限接口返回 **403（不是 401）**
- ✅ super_admin 跳过权限检查
- ✅ accessToken 过期后，前端通过 refreshToken 自动续签

### 5.5 前端实现阶段

后端骨架差不多了，你已经知道要做哪些页面，需要的不再是"帮我想要做什么"，而是"**在页面目标已经明确的前提下，把它们做得更像成熟后台**"。这是 ui-ux-pro-max 真正发挥价值的时候。

```
/superpowers:execute-plan

执行 PLAN.md 中 Phase 3 的所有步骤，使用 ui-ux-pro-max 技能生成前端页面。

设计要求：
- 整体风格：SaaS 后台管理系统，Modern + Clean
- 配色：参考 SaaS 行业调色盘，主色深蓝（#1E40AF），辅色浅灰
- 字体：Inter + 系统字体栈
- 组件库：HeroUI，不自造轮子
- 侧边栏：固定宽 272px，图标 + 文字，按后端返回的菜单动态渲染
- 表格：带分页、搜索和行级操作
- 表单弹窗：Drawer 风格（右侧滑入），不用居中 Modal
- 权限分配：Checkbox 树形结构，按系统 / 菜单 / 权限分组

页面清单：
1. 登录页（/login）
2. 用户管理（/users）
3. 角色管理（/roles）
4. 权限配置中心（/permission-center）
5. 个人信息（/profile）
```

前端权限控制示例：

```typescript
// store/auth.store.ts
const hasPermission = (permission: string) => {
  if (!user) return false;
  if (user.isSuperAdmin) return true;

  const permissions = Array.isArray(user.permissions)
    ? user.permissions.map((p) =>
        typeof p === 'string' ? p : p.code)
    : [];

  return permissions.includes(permission);
};
```

```tsx
// 按钮级权限控制
{hasPermission('user:delete') && (
  <Button variant="ghost"
    onClick={() => setDeleteConfirmUser(userItem)}>
    删除用户
  </Button>
)}

// 菜单级权限控制
const visibleMenus = menus.filter(
  (menu) => menu.visible && !menu.parentId,
);
```

前端验收清单：
- ✅ 菜单根据权限动态显示/隐藏
- ✅ 未登录用户不能进入后台页面
- ✅ 没权限的按钮不展示
- ✅ 权限分配界面能正常保存
- ✅ 禁用用户无法登录

### 5.6 集成与交付阶段

很多教程写到前后端页面都出来就结束了，但**真实项目恰恰是在集成阶段开始变难**。

```
/superpowers:execute-plan

执行 PLAN.md 中 Phase 4 的集成步骤：

1. 前后端联调：
   - 配置 NEXT_PUBLIC_API_URL，默认 http://localhost:4002/api
   - 封装 axios 实例，自动注入 Bearer Token，处理 401 自动刷新
   - 统一错误处理（401 跳转登录页，403 由页面按业务场景提示）

2. 本地启动：
   - user-system 服务（NestJS，4002）
   - admin-web 服务（Next.js，3001）
   - packages/database 负责 Prisma Schema、迁移和种子数据

3. 初始化脚本：
   - 自动创建后台管理系统、内容管理系统和 Chat 系统
   - 自动创建 super_admin 用户和初始角色
   - 自动写入菜单、权限和角色授权关系

完成后输出完整的 README，包含本地启动步骤。
```

集成验收：

```bash
bun run dev:user
bun run dev:admin

# 初始化数据（运行一次）
bun --cwd packages/database run db:seed

# 前端登录后用 Token 调后端
curl http://localhost:4002/api/users \
  -H "Authorization: Bearer <tokenFromFrontend>"
```

最终验收标准：
- ✅ user-system 和 admin-web 本地服务正常启动
- ✅ 初始化脚本正常写入权限和管理员账号
- ✅ 前端登录后 Token 注入正常，接口可访问
- ✅ 401 自动刷新或跳转登录页
- ✅ 配置项集中在环境变量和包脚本中

---

## 六、适用场景与现实限制

### 6.1 真正适合的场景
- 中大型功能开发：牵涉模型、接口、页面、测试的完整模块
- 多模块联动：前后端、交互、鉴权、配置、联调协同推进
- 需要跨 session 续做
- 需要复盘与审计：知道设计怎么定的、每步做到哪、为什么这样做

### 6.2 不适合全流程的场景
- 修一个很小的 bug
- 一次性脚本
- 快速验证想法的原型
- 需要边做边改方向的创意型任务

> **一句话：小任务轻流程，大任务重流程。**

### 6.3 现实限制
- **Spec / Plan 有前置成本**：任务很小时，花十几分钟对齐、写文档、拆计划可能不划算
- **TDD 让 AI 显得更慢**：结果更可验证，代价是节奏不如"直接写一版能跑的"快
- **ui-ux-pro-max 效果依赖代码基线**：仓库组件体系混乱、设计 token 失控，它的上限也会被拉低
- **人工决策不可替代**：Skill 能加强执行，但不能替你决定哪些复杂度该引入、哪些边界这次不做、什么时候求快什么时候求稳

---

## 七、小结：把 AI 放回工程节奏里

工程底座只是起点。真正进入功能开发时，需求边界会摇摆，前后端会互相影响，权限模型多想一步就会膨胀，页面能用却不一定像成熟后台。

RBAC 例子里关键的不是"AI 生成了多少文件"，而是这几件事有没有稳住：

1. **需求边界先收窄**，别让模型顺手加出一套企业级权限平台
2. **Spec 先把核心决策写死**，后面的 Plan 才不会拆得越细越偏
3. **后端先跑通可验证骨架**，接口、权限、初始化数据和 curl 验收都要落地
4. **前端等页面目标和接口形态明确后再打磨**，否则设计增强只是给不稳定的需求套皮
5. **集成阶段单独处理**，Token 注入、401/403、启动脚本和种子数据不能留到最后"顺手补"

> 第二章解决"工程怎么搭起来"，这一章解决"AI 怎么参与开发"，第三章开始解决"模型能力怎么进入系统"。

---

## 八、延伸：跑完整流程时要关注模型成本

用 Superpowers 推进大任务、用 ui-ux-pro-max 打磨前端，本质都是让模型做更多事，Token 消耗和模型选型的代价会变得具体：

- 哪些阶段必须用强模型，哪些可以切到更便宜的小模型？
- 缓存命中率有多少？Prompt 前缀是否足够稳定？
- 每一步的输入、输出、缓存 Token 分别多少？
- 优化上下文后，成本到底降了多少？

> Agent 工程不只是"能不能生成"，还包括"能不能长期、稳定、可控地运行"。（第十章 Token 经济学会展开）

---

## 九、下一章

下一章正式进入 LangChain：不再讨论"怎样让 AI 帮我们写代码"，而是把模型调用本身接进 Nest 服务端，整理成可维护、可测试、可复用的能力链路。

- 这一章：AI 怎么更稳地参与开发
- 下一章：AI 能力怎么真正进入服务端
