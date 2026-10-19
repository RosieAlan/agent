# D04第一块：模型调用限时与失败响应

2026-10-19用户明确“继续D4”，按授权进入D04；D02/D03综合验收留记录。原课程来源：1.5.6异常处理、1.6.7校验/兜底/重试，3.4.5请求边界与超时、第二章Service组织；第六章流式与第十六章日志在本单元后续展开。主课目标：超时/取消；重试/限流；SSE结束/异常/断连；配置/脱敏日志。当前完整功能为后端单次业务模型调用限时，手动取消与浏览器断连传递在下一块。

## 达标目标

必背：后端为模型调用设置等待期限，把AbortSignal传给支持取消的调用；时间到后中止本地等待/传输并返回504。会用：解释invoke第一个参数为消息，第二个为本次调用配置；把signal传到结构化封装。了解：取消为协作机制，供应商计算和计费是否终止取决于供应商；事件循环阻塞可能延迟计时处理。

## 业务问题与路径

已有页面提交→Controller输入校验→Service模型调用→结构校验→返回对象。超时控制覆盖本例structuredModel.invoke开始到完成，包括封装的响应处理；模板构建前的处理不纳入这30秒。30秒是课堂示例值，实际按时延目标、模型与资源配置。

正常30秒内完成→现有POST返回201；到期限→取消信号触发→调用抛错→Service转换GatewayTimeoutException→Nest返回504→页面显示状态和说明。HTTP400仍表示用户输入未通过校验。暂保留其他异常原样抛出，D04后续细分401/404/429与解析失败。

## 新API逐项解释

AbortSignal是Node22内置全局对象；timeout毫秒参数返回新signal，创建时开始计时，每次请求各创建一次。30_000与30000等值，下划线方便读数字。signal.aborted初始false，到期true；信号需要传给支持取消的API才能通知它结束操作。

structuredModel.invoke(messages,{signal})：参数一是消息，参数二是LangChain本次调用配置，signal由封装向模型/请求层传递。本地OpenAI适配器支持该配置，需对实际适配器验证。GatewayTimeoutException来自@nestjs/common，抛出后由Nest映射为HTTP504。

return await使异步调用失败发生在当前try范围内，catch可以执行超时分类。return promise直接退出try会使之后的异步拒绝绕过这里的catch。throw error将其余异常继续交给上层，保留原错误信息用于后续分类。

## 学生完整替换文件

文件chapter-02-工程底座/llm/services/chat/src/llm/requirement.service.ts。学生替换为下面完整代码；当前字段与Prompt继续复用，无需复制Schema。

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

  async extract(input: string): Promise<RequirementResult> {
    const messages = await requirementPrompt.formatMessages({ input });
    const structuredModel = this.model.withStructuredOutput(
      RequirementResultSchema,
    );
    const signal = AbortSignal.timeout(MODEL_TIMEOUT_MS);

    try {
      return await structuredModel.invoke(messages, { signal });
    } catch (error) {
      if (signal.aborted) {
        throw new GatewayTimeoutException('模型响应超过30秒，请稍后再试');
      }
      throw error;
    }
  }
}
```

与前端只关闭loading分别理解：loading负责界面状态；signal送入后端模型调用后才能请求中止本地传输。Promise.race只决定先观察哪个Promise的完成/失败，另一项仍会运行；应明确调用下层支持的取消接口。超时触发发起取消请求，供应商侧是否停止生成/计费需供应商支持，不能宣称绝对零费用。

## 验证与作业

学生在services/chat执行bun run typecheck，再沿用http://localhost:3002/d03提交普通需求。30秒内完成保持201及已有结果字段；超时应显示504和模型响应超过30秒。未遇到真实慢请求时只登记正常路径，超时分支可先用教师固定慢响应验证；后续本单元补浏览器可控失败验证。无须为了制造超时把真实调用期限缩到1毫秒。

教师仅使用本地固定响应验证signal传递、正常结果、到期错误映射、非超时错误原样抛出，真实供应商调用0次。运行结果验证与代码语法/类型验证分别登记。

## 面试题和标准答案

1. 页面停止等待是否代表上游请求已取消？页面状态负责展示；后端要接收到取消并把signal传给实际模型调用，供应商侧取消需相应支持。
2. 为什么将signal放invoke第二参数？第一参数属于业务消息，第二参数控制本次运行；signal属于运行配置。
3. 设置30秒后，模型10秒完成会怎样？正常返回原结果；本次signal稍后触发不会追溯改变已返回结果。
4. 为什么超时用504？该服务等待上游模型响应超过了约定期限；业务协议可自定义错误码，本例用Nest异常映射。

## 课末检查

学生完成代码与正常页面运行；解释signal放哪、只关loading时后端会怎样。后续按顺序补浏览器手动取消→后端断连传播与原因分类，再做重试/限流、SSE和日志；D04全部主题与独立运行齐备后才完成验收。

官方资料：https://nodejs.org/download/release/v22.17.0/docs/api/globals.html#static-method-abortsignaltimeoutdelay 、 https://reference.langchain.com/javascript/langchain-core/language_models/base/BaseLanguageModelCallOptions/signal

## 本轮验证记录

教师本轮验证5项通过：讲义TypeScript语法转换、实际ChatOpenAI结构化封装固定响应返回、signal传到模拟HTTP层、50ms到期映射504、非超时异常原样保留。初版模拟响应未兼容JSON Schema模式后已修正测试桩并重跑通过，业务代码未改；联网供应商请求0次。学生Service修改、类型检查与页面结果待交。
