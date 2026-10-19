# D03第五块：浏览器联调与输入边界

对应原3.9.1–3.9.3的后端分工、验证和页面消费；承接3.7。学生Controller实际代码已核对，safeParse失败抛BadRequestException，成功才执行Service。services/chat运行bun run typecheck通过。当前无3002/4001/4002监听；教师尚未启动HTTP服务或请求真实模型。

## 学习目标

能在浏览器观察正常结果与400错误；解释fetch对HTTP错误的行为；能独立补空白输入校验。前端沿用当前Next/React工程，只增加独立练习页面，由学生创建；原聊天页面和共享组件保持原状。

## 页面代码先解释

use client声明交互页面可使用状态和浏览器事件。useState是React保存页面状态的函数，返回当前值和更新函数；setInput类似更新Vue中的响应式变量。onChange处理输入变化，onClick处理点击。send接收本次要发送的请求体，三个按钮分别传合法文本、数字和空字符串。

fetch发送HTTP请求；response.status记录状态码；response.json解析JSON，格式/事实校验仍各自执行。fetch对于400/500仍可返回Response，所以页面应读取状态码；此处把成功和错误响应统一展示，方便观察。catch处理网络或JSON解析失败；finally恢复按钮。生产业务可用response.ok分别处理成功和失败，response.ok表示200至299。

## 学生创建完整文件

路径：chapter-02-工程底座/llm/clients/chat-web/src/app/d03/page.tsx。目录d03不存在时由学生创建。此为长期课程练习，学生自己复制。

```tsx
'use client';

import { useState } from 'react';

export default function D03Page() {
  const [input, setInput] = useState('用户注册时必须绑定手机号，密码至少8位。');
  const [output, setOutput] = useState('等待提交');
  const [loading, setLoading] = useState(false);

  async function send(body: unknown) {
    setLoading(true);
    setOutput('请求中……');
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/langchain/structured`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        },
      );
      const data = await response.json();
      setOutput(`HTTP ${response.status}\n${JSON.stringify(data, null, 2)}`);
    } catch (error) {
      setOutput(error instanceof Error ? error.message : '请求失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 800, margin: '40px auto', padding: 24 }}>
      <h1>D03：结构化需求接口</h1>
      <textarea
        aria-label="需求原文"
        rows={4}
        value={input}
        onChange={event => setInput(event.target.value)}
        style={{ width: '100%', border: '1px solid #888', padding: 12 }}
      />
      <div style={{ display: 'flex', gap: 16, margin: '16px 0' }}>
        <button disabled={loading} onClick={() => send({ input })}>提交需求</button>
        <button disabled={loading} onClick={() => send({ input: 123 })}>验证数字输入</button>
        <button disabled={loading} onClick={() => send({ input: '' })}>验证空字符串</button>
      </div>
      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{output}</pre>
    </main>
  );
}
```

现有next.config.ts设置NEXT_PUBLIC_API_BASE_URL，默认http://localhost:4001；当前main.ts默认允许3002来源。本练习直接调用4001结构化接口，现有工作台代理只允许会话等指定路径。现有structured入口未配置本方法鉴权，此练习调用无需4002登录服务；正式鉴权接口继续保留既有方案。

启动：在chapter-02-工程底座/llm执行bun run dev，根脚本同时启动chat与chat-web，前端等待4001后启动3002。该项目后端包含Prisma初始化，现有数据库等依赖需可用；若启动报错，应按实际日志定位，当前未声称环境已启动。浏览器打开http://localhost:3002/d03。

## 验收顺序和预期

1. 先点数字输入：HTTP400，提示input必须是非空字符串。
2. 点空字符串：HTTP400；这两类失败在模型调用前拦截。
3. 点提交需求：进入真实模型请求，成功默认HTTP201并显示action/constraints/entities；记录原文依据。
4. 独立修改packages/contracts/src/index.ts中输入字段，改为input:z.string().trim().min(1)。trim先去掉首尾空白，min再检查长度；Schema成功返回的是处理后的data。把输入框内容清空，再按三次空格提交，应HTTP400。无需先提交未修正的空格请求，避免无意义模型调用。

共享包变更若开发进程未加载，重启本次bun run dev的终端进程后再验证。接口400可在Network查看Response；连接失败先看4001是否启动/CORS；201格式正确内容偏差则检查后端提示词与原文。

## 面试与必背答案

输入Schema在调用模型前拦截无效请求；输出Schema约束模型结果类型；业务检查核对原文事实。前端同时观察HTTP状态与响应体，fetch返回Response后自行判断业务分支。trim().min(1)按先裁剪空白再检查长度执行，合法输入从checked.data读取。

检查题：数字为什么400而正常文本可能201？分别走输入失败与正常POST成功分支。输出至少6位为什么还可能返回成功？Schema只检查当前字段类型，业务事实需额外核查。完整D03综合修改随后新增missingInformation字段并检查上下游，当前本轮只验输入边界。

## 当前进度

D03模板、文本链、结构化链真实运行通过；Controller代码已读、后端类型检查通过；本页学生创建、实际HTTP正常/非法/空白验证及综合修改仍待交。D03整体未完成，独立通过1/32，课程分数待测。教师不会自动发起付费模型调用。
