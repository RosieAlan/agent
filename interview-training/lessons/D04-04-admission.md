# D04第四块：限制请求频率与同时处理数量

2026-10-20。原课程第二章Service能力封装、第一章1.6.7失败处理承接；结合招聘要求中的并发控制、限流和成本控制补充工程实作。原课程Token经济学的Token预算与模型费用在D24完整展开，本课先控制业务请求量。

## 上一块纠正与标准答案

maxRetries属于当前LangChain模型适配器配置，限制额外尝试次数，间接约束请求次数、时延和潜在费用。maxRetries=2最多首次加两次重试。失败请求是否产生Token费用取决于供应商处理进度及计费规范；首次请求本身也有用量。LangGraph节点重试使用retryPolicy等节点选项，其中maxAttempts包含首次，具体节点实现到D09/D10讲解。两层都启用时要核对叠加次数。

学生已修改模型工厂和Service的maxRetries，教师本轮后端非增量类型检查通过；正常页面结果及独立解释待验收。本块继续按用户要求推进。

## 目标与一个具体场景

必背：频率限制控制一段时间内接收多少次；并发限制控制此刻同时处理多少个。先检查再进入模型调用，任务结束或失败后在finally归还并发名额；重试消耗上游调用次数，仍属于同一个业务任务。

本练习采用一个Node进程、一个默认单例Service的全部用户共享限制：从当前计数窗口起每10秒最多接收5个业务请求；同时最多处理2个。超额立即返回429。阈值为教学示例，实际根据模型配额、耗时和业务容量测定。

例：A、B正在等模型，C此时提交，C收到429；A结束后，D可以进入。即使前几个请求都很快结束，在同一个10秒窗口已接收5个时，第6个仍收到429。并发看当前未完成数量，频率看窗口内已接收数量。

## 新写法先解释

- HttpException和HttpStatus来自@nestjs/common：new HttpException(提示, HttpStatus.TOO_MANY_REQUESTS)交由Nest返回429。本地过载和供应商429来源不同，需要结合日志与提示区分。
- Date.now()为JS内置，返回当前毫秒时间；now-windowStartedAt表示当前窗口已经过去多久。本例按窗口到期后收到的下一次请求重置计数，使用懒重置，无额外定时器。
- private字段保存在当前Service对象上。Nest默认单例Provider在同一进程复用该实例，多个请求会读写同一份计数。
- ++增加1，--减少1。activeRequests表示已接收且尚未结束的任务数；windowRequestCount表示本窗口已接收的任务数。
- clientSignal?.throwIfAborted()调用取消信号的内置检查，已取消就抛错；没有传signal时跳过。发起和结束等待的取消机制继续沿用前两块。

## 学生修改：完整Service

替换chapter-02-工程底座/llm/services/chat/src/llm/requirement.service.ts。模型工厂保持上一块修改，Controller和页面保持当前代码。

```ts
import {
  GatewayTimeoutException,
  HttpException,
  HttpStatus,
  Injectable,
} from '@nestjs/common';
import {
  RequirementResultSchema,
  type RequirementResult,
} from '@autix/contracts';
import { createChatModel } from './model.factory.js';
import { requirementPrompt } from './requirement.prompt-builder.js';

const MODEL_TIMEOUT_MS = 30_000;
const RATE_WINDOW_MS = 10_000;
const MAX_REQUESTS_PER_WINDOW = 5;
const MAX_CONCURRENT = 2;

@Injectable()
export class RequirementService {
  private model = createChatModel({ maxRetries: 2 });
  private activeRequests = 0;
  private windowStartedAt = Date.now();
  private windowRequestCount = 0;

  async extract(
    input: string,
    clientSignal?: AbortSignal,
  ): Promise<RequirementResult> {
    clientSignal?.throwIfAborted();

    const now = Date.now();
    if (now - this.windowStartedAt >= RATE_WINDOW_MS) {
      this.windowStartedAt = now;
      this.windowRequestCount = 0;
    }
    if (this.windowRequestCount >= MAX_REQUESTS_PER_WINDOW) {
      throw new HttpException('请求过于频繁，请稍后再试', HttpStatus.TOO_MANY_REQUESTS);
    }
    if (this.activeRequests >= MAX_CONCURRENT) {
      throw new HttpException('当前分析任务较多，请稍后再试', HttpStatus.TOO_MANY_REQUESTS);
    }

    this.windowRequestCount++;
    this.activeRequests++;

    const timeoutSignal = AbortSignal.timeout(MODEL_TIMEOUT_MS);
    const signal = clientSignal
      ? AbortSignal.any([clientSignal, timeoutSignal])
      : timeoutSignal;

    try {
      const messages = await requirementPrompt.formatMessages({ input });
      signal.throwIfAborted();
      const structuredModel = this.model.withStructuredOutput(RequirementResultSchema);
      return await structuredModel.invoke(messages, { signal });
    } catch (error) {
      if (timeoutSignal.aborted && signal.reason === timeoutSignal.reason) {
        throw new GatewayTimeoutException('模型响应超过30秒，请稍后再试');
      }
      throw error;
    } finally {
      this.activeRequests--;
    }
  }
}
```

## 按一次请求读代码

1. 用户输入先在Controller通过Schema校验，再进入extract。已经取消的请求在开头结束。
2. 窗口到期就重置起点和已接收次数。检查频率、再检查当前并发数量；超额抛429，后面的模型调用不会执行。
3. 接收请求后，窗口计数和并发计数各加1。检查与加1之间没有await，在当前JS进程中连续执行，其他请求不会在此同步片段中间插入。
4. 进入try，构建消息并调用模型，沿用超时、取消和模型请求重试。格式化、模型调用、结构解析任一步抛错，都会进入finally，归还并发名额。
5. windowRequestCount保留本窗口的已接收记录，成功、失败或取消都已经占用过接收额度；activeRequests只统计当前未完成任务，所以结束时减1。被拒绝的请求在加1前退出，本例不计入已接收额度。

重要位置：计数放在Service字段可跨请求复用；写在extract内部的局部let变量会每次从0开始。activeRequests减1放在finally，覆盖成功、失败和取消；等待模型的return await使finally在调用结束后执行。

## 范围与后续工程方案

该实现控制单进程内这一个Service的整体业务接收量。5个业务请求、每个maxRetries=2，最坏可能有15次模型请求，所以入口请求限流与上游模型调用配额需要分别考虑；Token数另设预算。重启进程会清空计数；多进程、多副本各有自己的计数。跨副本限制需要共享存储和原子操作，Redis/网关方案在后续工程化单元完善；按用户限流须用后端验证身份得到的用户ID。

本例使用固定窗口，窗口边界前后可能短时间合计接收接近两倍额度。滑动窗口关注最近连续一段时间；令牌桶按速率补充额度并允许有上限的短时突发。这三种算法作为设计取舍掌握，本块实作固定窗口。正式Nest接口还可用@nestjs/throttler配置按来源的频率限制；其Guard在进入Controller前检查，当前手写例便于追踪计数，不引入额外依赖。

超额策略可选拒绝、有限排队或降级，本例选择立即429，页面现有HTTP状态展示可直接显示提示。若设计排队，要限制队列长度、等待时长并处理排队取消。当前重试退避期间任务仍占并发名额，直到invoke实际结束；上一课测得退避取消返回延迟仍保留D04综合排错。

## 学生作业与参考答案

1. 复制完整Service，运行bun x tsc --noEmit --incremental false。浏览器正常提交一次，已有结构化结果与取消功能继续验收。集中并发和频率边界由教师用固定响应验证，无需连续付费请求制造429。
2. 独立把MAX_CONCURRENT改成1，说明两个请求几乎同时到达且第一个还未结束时的结果。答案：第一个进入，第二个收到并发429，第二个不调用模型。
3. 第一个请求抛错后新请求能否进入？答案：finally减1归还名额；仍需满足当前窗口频率额度。
4. 窗口额度5，先后已有5个成功结束请求，第6个能否进入？答案：窗口未到期时返回频率429，即使activeRequests=0。窗口到期后重新开始计数。
5. 为什么取消后窗口次数保持？答案：窗口记录已经接收的业务请求，任务曾占用资源；并发名额随任务实际退出归还。

## 面试题及完整答案

1. 重试、限流和并发控制怎样组合？入口控制接收频率和并发容量，接收后在取消/总期限内做有限请求重试，finally释放当前任务名额；另核对上游RPM/TPM、Token预算与多层重试叠加。
2. 为什么单线程Node还要并发控制？多个请求可以交替等待网络，进程内会同时存在多个尚未完成的任务，供应商连接、内存和配额都有限。
3. 多副本为什么内存计数不够？每个进程维护独立计数，整体请求量会叠加；共享存储或网关需保证检查/占用原子性，任务结束或租约到期要有释放策略。
4. 频率和并发有什么区别？频率数一段时间内接收多少次；并发数此刻还有多少个未结束。请求很慢时频率不高也可能积累大量并发，请求很快时并发低也可能产生很高频率。

## 验证与进度

教师对讲义Service配固定模型/可控时钟验证：第三个并发429且不调用模型、完成后恢复、第五次后频率拒绝、窗口到期恢复、异常释放、取消释放、已取消请求不占名额、格式化失败释放、超时504及释放、重试期间维持业务名额。拟议Service虚拟源码类型检查通过，供应商请求0次；学生实际修改和页面结果待交。

D04当前讲到频率/并发控制，剩余SSE完成/错误/断连、配置与脱敏日志、退避取消边界及综合验收。整体独立通过1/32；D02/D03综合缺口保留，课程独立评分待测。

资料：[Nest频率限制](https://docs.nestjs.com/security/rate-limiting)、[LangGraph节点重试配置](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph)。
