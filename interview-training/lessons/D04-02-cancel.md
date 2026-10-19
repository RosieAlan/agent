# D04第二块：点击取消后，把取消信号传到模型调用

日期：2026-10-19。原课程对应：第一章异常处理与请求边界、第三章3.4.5流式请求的中断问题、第六章前后端交互。当前先用已有JSON接口学清取消传递；SSE断连在本单元后续接续。学生修改业务文件，教师维护讲义并做本地模拟验证。

## 本块目标与必背答案

必背：页面通过AbortController取消fetch；后端监听响应连接提前关闭，触发自己的AbortController；Service把客户端取消和模型超时合成一个signal，传给invoke的第二个参数。每层收到信号后配合停止等待或传输，供应商侧计算与计费取决于其支持。

至少会用：沿着页面→Controller→Service指出每一处signal从哪里来、传到哪里；正常完成返回201，模型等待到期返回504，主动取消由页面显示“已取消本次请求”。了解：取消信号首次触发的reason用于区分原因；正常响应结束也会关闭连接，需要用writableEnded判断。

## 先看完整过程

用户在/d03点提交，浏览器fetch等待后端；后端Service等待模型。用户中途点取消，浏览器调用controller.abort()，fetch停止等待并取消传输。后端观察到响应连接提前关闭，调用后端自己的controller.abort()。Service收到取消信号，LangChain再把它传给底层请求。

浏览器与后端各自创建AbortController，网络连接把两边的取消行为衔接起来。浏览器对象仅存在浏览器内存中，后端对象仅存在后端进程中。

## 新API：先认识，再改文件

| 写法与来源 | 作用 | 参数与返回/执行时机 |
| --- | --- | --- |
| new AbortController()，浏览器/Node内置 | 创建手动取消控制器 | 无参数，返回控制器；每次请求创建一个 |
| controller.signal | 将取消信号交给调用方 | 属性值是AbortSignal；传给fetch/invoke |
| controller.abort(reason) | 发出取消通知 | reason可省略；调用时触发，返回undefined |
| useRef，React | 在页面重新渲染后仍保存本次控制器 | 初始null；返回带current属性的对象，写current自身不会触发渲染 |
| @Res({passthrough:true})，NestJS | 访问底层Response，同时保留Nest对返回对象的序列化 | 注入当前请求对应的Response |
| res.on('close',fn)，Node HTTP | 连接关闭时执行fn | 注册监听；提前断连和正常结束都可能出现close |
| res.writableEnded | 检查服务端是否已经调用end结束响应 | 布尔值；只表达服务端响应结束状态 |
| res.off('close',fn) | 清理刚才注册的监听 | 在finally执行 |
| AbortSignal.any(signals)，Node22 | 合并多个取消来源 | 数组参数，返回新signal；任意来源触发就触发，reason保留最先来源的原因 |

loading继续用useState，负责按钮和页面显示；requestRef保存正在进行的请求控制器。两个变量各有用途。

## 修改1：Service完整替换

文件：chapter-02-工程底座/llm/services/chat/src/llm/requirement.service.ts。保留已有模板、模型工厂和共享Schema。

```ts
import { GatewayTimeoutException, Injectable } from '@nestjs/common';
import {
  RequirementResultSchema,
  type RequirementResult,
} from '@autix/contracts';
import { createChatModel } from './model.factory.js';
import { requirementPrompt } from './requirement.prompt-builder.js';

const MODEL_TIMEOUT_MS = 30_000;

@Injectable()
export class RequirementService {
  private model = createChatModel();

  async extract(
    input: string,
    clientSignal?: AbortSignal,
  ): Promise<RequirementResult> {
    const messages = await requirementPrompt.formatMessages({ input });
    const structuredModel = this.model.withStructuredOutput(
      RequirementResultSchema,
    );
    const timeoutSignal = AbortSignal.timeout(MODEL_TIMEOUT_MS);
    const signal = clientSignal
      ? AbortSignal.any([clientSignal, timeoutSignal])
      : timeoutSignal;

    try {
      return await structuredModel.invoke(messages, { signal });
    } catch (error) {
      if (timeoutSignal.aborted && signal.reason === timeoutSignal.reason) {
        throw new GatewayTimeoutException('模型响应超过30秒，请稍后再试');
      }
      throw error;
    }
  }
}
```

extract第一个参数input仍是用户文本；新增的第二个参数clientSignal由Controller传入。问号表示可选，其他只传input的旧调用仍可使用。函数内部仍保留模型30秒期限；本次调用同时接受“用户取消”和“等待到期”两个来源。

catch判断最先触发的原因：timeoutSignal先触发时返回504；用户取消先触发时原样把异常交给Controller处理。比较reason还能避免“用户先取消，稍后计时器到期”被误归为模型超时。

## 修改2：只替换Controller里的structured方法

文件：chapter-02-工程底座/llm/services/chat/src/llm/llm.controller.ts。现有文件已经导入Res和express的Response类型，其他接口保留。

```ts
  @Post('structured')
  async structured(
    @Body() body: unknown,
    @Res({ passthrough: true }) res: Response,
  ) {
    const checked = RequirementSchema.safeParse(body);
    if (!checked.success) {
      throw new BadRequestException('input必须是非空字符串');
    }

    const controller = new AbortController();
    const onClose = () => {
      if (!res.writableEnded) {
        controller.abort(new Error('客户端已断开连接'));
        console.info('[structured] 客户端断开，已向模型调用发送取消信号');
      }
    };
    res.on('close', onClose);

    try {
      return await this.requirementService.extract(
        checked.data.input,
        controller.signal,
      );
    } catch (error) {
      if (controller.signal.aborted) return;
      throw error;
    } finally {
      res.off('close', onClose);
    }
  }
```

这段沿用已有输入校验。onClose中的判断表示：连接已经关闭，而且服务端响应尚未正常结束，此时向Service发取消通知。示例使用响应res的close事件；请求对象的close事件还涉及请求体读取完成，直接套用容易过早触发取消。

Controller在客户端断连后结束处理；浏览器已经自行显示取消结果。其他异常继续交给Nest处理，超时路径仍输出504。finally在完成与失败时都清理当前监听。演示日志仅记录取消动作；生产环境结构化日志及requestId在D04后续补齐。

## 修改3：练习页面完整替换

文件：chapter-02-工程底座/llm/clients/chat-web/src/app/d03/page.tsx。保留原/d03地址以及合法、数字、空字符串三个检查入口。

```tsx
'use client';

import { useRef, useState } from 'react';

export default function D03Page() {
  const [input, setInput] = useState('用户注册时必须绑定手机号，密码至少8位。');
  const [output, setOutput] = useState('等待提交');
  const [loading, setLoading] = useState(false);
  const requestRef = useRef<AbortController | null>(null);

  async function send(body: unknown) {
    if (requestRef.current) return;
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setOutput('请求中……');

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/langchain/structured`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal,
        },
      );
      const data = await response.json();
      setOutput(`HTTP ${response.status}\n${JSON.stringify(data, null, 2)}`);
    } catch (error) {
      setOutput(
        controller.signal.aborted
          ? '已取消本次请求'
          : error instanceof Error ? error.message : '请求失败',
      );
    } finally {
      requestRef.current = null;
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 800, margin: '40px auto', padding: 24 }}>
      <h1>D04：结构化需求接口与请求取消</h1>
      <textarea
        aria-label="需求原文"
        rows={4}
        value={input}
        onChange={event => setInput(event.target.value)}
        style={{ width: '100%', border: '1px solid #888', padding: 12 }}
      />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, margin: '16px 0' }}>
        <button disabled={loading} onClick={() => send({ input })}>提交需求</button>
        <button disabled={loading} onClick={() => send({ input: 123 })}>验证数字输入</button>
        <button disabled={loading} onClick={() => send({ input: '' })}>验证空字符串</button>
        <button disabled={!loading} onClick={() => requestRef.current?.abort()}>
          取消本次请求
        </button>
      </div>
      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{output}</pre>
    </main>
  );
}
```

requestRef.current先检查本次请求是否仍在执行，避免连续点击重复发出。send开始保存控制器，取消按钮调用这个控制器的abort，finally恢复按钮并清空引用。React重新渲染时useRef继续保留同一个引用，所以下一次按钮点击仍能找到本次控制器。

## 浏览器验收与独立练习

1. 前后端各执行bun x tsc --noEmit --incremental false，类型检查通过后，打开http://localhost:3002/d03。
2. 正常提交注册需求，预期201和结构化对象；数字、空字符串预期400。
3. 再提交一次，后端开始处理后在返回前点击取消。页面显示“已取消本次请求”，按钮恢复可用；后端出现本课取消日志。若请求已返回，取消按钮恢复禁用，按正常完成登记。
4. 取消后再提交，预期新请求能够正常完成。教师本地慢响应验证覆盖取消路径，学生真实模型运行只按实际需要发起。
5. 独立解释：某页面点取消后只执行setLoading(false)，后端还在等待模型，应该补哪几处？指出浏览器fetch.signal、响应断连监听、Service合并signal与invoke传递。

课后扩展题：30秒先到，随后客户端断连，signal.reason保留哪个原因？答案：保留先到的超时原因；客户端若已经断开，当前HTTP响应已无法送达浏览器。原因分类与响应是否送达分别判断。

## 面试题与完整答案

1. 如何做Agent请求取消？前端AbortController取消fetch；后端监听响应提前关闭，把取消传给业务Service和模型适配器；同时设置超时，释放监听等资源。涉及工具执行时每个支持取消的工具也要接收信号，写入类操作还需幂等与结果核对，工具细节在D06之后展开。
2. 为什么取消页面后后端还可能执行？前端和后端各有执行过程，取消需要沿连接、Controller、Service、模型请求逐层传递；已经完成的操作保留原结果。供应商计算与费用按其取消支持判断。
3. 用户取消和模型超时如何区分？保留不同信号来源，用合成signal的首次reason判断；本例模型超时映射504，断连由Controller结束处理，页面在本地展示取消。
4. 为什么在finally移除监听？正常完成、取消和异常都会进入finally，统一清理当前请求注册的资源，避免后续事件触发已结束任务的逻辑。

## 教师验证记录与进度

本轮学生已写上一块Service，后端非增量TypeScript检查通过。新课代码由学生按上面三处修改；教师以Node22本地HTTP模拟验证正常201、浏览器abort、后端等待取消、超时504、监听清理、首次reason保留6项，全部通过；新讲义代码另做语法转换检查。真实模型供应商请求0次。该模拟证明示例取消路径，项目三文件实际接入待学生完成后验收。

D04正在学习超时/取消主题；剩余重试/限流、SSE完成/错误/断连、配置/脱敏日志以及综合验收。D01独立通过，D02/D03已有讲授与真实运行证据、综合验收待收尾；总体独立通过1/32，课程独立分数待测。

官方资料：[Node22取消信号](https://nodejs.org/download/release/v22.17.0/docs/api/globals.html#static-method-abortsignalanysignals)、[Node响应close事件](https://nodejs.org/download/release/v22.17.0/docs/api/http.html#event-close_2)、[NestJS passthrough](https://docs.nestjs.com/controllers#library-specific-approach)、[浏览器AbortController.abort](https://developer.mozilla.org/en-US/docs/Web/API/AbortController/abort)。
