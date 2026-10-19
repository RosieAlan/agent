# D03第四块：从结构化脚本到后端接口

来源原3.7.2–3.7.3及第二章NestJS工程底座；后续接原3.9业务页面。学生上一块真实结构化结果正确，constraints数组规则口述正确。本次先追踪现有接口，再由学生给接口补输入校验，接着浏览器联调与独立新增字段。教师本轮维护讲义，业务源码保持学生操作。

## 必背与目标

Controller接收HTTP请求并返回响应；Service组织模板和模型调用；共享contracts定义输入输出字段和类型。输入校验检查前端发来的数据，输出校验检查模型返回的数据，事实检查核对原文依据。能用具体注册请求追踪上述完整路径。

上一题细化：z.array(z.string())定义字符串数组，describe解释含义；model.withStructuredOutput(RequirementResultSchema)配置结构化结果解析校验；chain.invoke实际触发调用。

## 当前项目已经存在的文件

根目录为chapter-02-工程底座/llm。

- packages/contracts/src/index.ts：输入RequirementSchema与输出RequirementResultSchema，以及RequirementResult类型。
- services/chat/src/llm/llm.controller.ts：已有POST structured接口，类前缀api/langchain。
- services/chat/src/llm/requirement.service.ts：已有extract方法，生成模板消息，调用结构化模型。
- services/chat/src/llm/requirement.prompt-builder.ts：已有模板，复用prompts/requirement.prompt.ts。
- services/chat/src/llm/llm.module.ts：注册Controller和两个Service。

实际入口POST http://localhost:4001/api/langchain/structured，main.ts默认端口4001，PORT配置可覆盖。当前POST按Nest默认成功201；后续需要统一200时可专门配置。此为独立练习接口，聊天/会话接口另有路径。

## 一个请求如何走完

浏览器提交{input:"用户注册时必须绑定手机号，密码至少8位。"} → LlmController.structured拿到body → 校验body → RequirementService.extract接收字符串 → 模板填入input → structuredModel.invoke请求模型并解析校验 → Service返回对象 → Controller返回对象 → Nest序列化JSON → 前端response.json获得对象。

当前源码Controller直接转调extract，输入Schema已定义但本方法尚未调用；没有发现main.ts配置全局输入校验。该方法的body:{input:string}为TypeScript标注，本身提供开发时检查。输入校验补齐后才能把数字input、缺少input等拦在模型调用之前。

## 先读现有Controller片段

以下是教学抽取片段，原LlmController还包含其他接口和Service依赖，按原文件阅读。

```ts
@Controller('api/langchain')
export class LlmController {
  // 原文件构造函数中由Nest传入requirementService等依赖。
  @Post('structured')
  async structured(@Body() body: { input: string }) {
    return this.requirementService.extract(body.input);
  }
}
```

Controller/Post/Body均来自@nestjs/common。@开头是装饰器语法：Controller登记公共路径；Post登记请求方法和路径后缀；Body取得请求体。Nest在启动时建立路由映射，请求到来时调用对应方法。方法名字structured用于代码调用，URL由装饰器组合。

构造函数的private readonly requirementService: RequirementService让Nest把已创建的Service对象传入并保存在this.requirementService属性。Injectable标记Service可由Nest管理和注入；Module的providers登记可提供的Service，controllers登记处理HTTP的类。默认作用域下Service实例通常由应用复用。

## Service逐步执行

当前extract(input:string):Promise<RequirementResult>表示参数为字符串，异步返回结果对象；Promise描述等待完成的结果类型。

1. requirementPrompt.formatMessages({input})把用户原文填入模板。
2. this.model.withStructuredOutput(RequirementResultSchema)配置结构化输出。
3. structuredModel.invoke(messages)执行模型调用与结果解析校验。
4. return把对象返回Controller，由框架处理JSON响应。

这与上一块prompt.pipe(structuredModel).invoke({audience,input})采用相同的核心步骤；项目模板使用input变量，练习模板额外使用audience变量。

## 学生实际修改：在模型调用前检查输入

编辑services/chat/src/llm/llm.controller.ts。保留原文件其他接口，只做两处局部改动。

原@nestjs/common导入增加BadRequestException；再导入已有共享Schema：

```ts
import { Body, Controller, Post, Res, BadRequestException } from '@nestjs/common';
import { RequirementSchema } from '@autix/contracts';
```

用下面完整方法替换原structured方法：

```ts
@Post('structured')
async structured(@Body() body: unknown) {
  const checked = RequirementSchema.safeParse(body);
  if (!checked.success) {
    throw new BadRequestException('input必须是非空字符串');
  }
  return this.requirementService.extract(checked.data.input);
}
```

unknown表示请求体需要先验证。safeParse成功返回{success:true,data}，失败返回{success:false,error}；本例失败时抛BadRequestException，由Nest转换为HTTP400；成功才执行extract。safeParse属于Zod；BadRequestException属于Nest。当前共享Schema为z.string().min(1)，空字符串失败，空格字符串仍通过，空白处理在独立修改中补充。

contracts是共享包名称，@autix/contracts通过项目工作区依赖引入。把规则放在共享包便于前后端复用同一字段定义；每个接口仍需实际执行运行时校验。输入Schema和输出Schema分别用于HTTP输入与模型结果。

## 失败处理及边界

请求体无input/input为数字/空字符串：本方法400，模型调用0次。正确输入：进入模型调用，成功默认201。供应商或结果解析异常：当前接口缺少专门异常映射时通常作为500处理；D04继续明确上游错误、超时和重试。原文8位却返回6位：属于业务事实偏差，输出Schema可通过，需要依据检查。

## 检查题与标准答案

1. {input:123}在何处拦截？RequirementSchema.safeParse失败，Controller抛400，Service不会执行。
2. Promise<RequirementResult>与withStructuredOutput分别检查什么？Promise类型服务TypeScript开发时检查；结构化封装处理实际模型结果的解析与校验。
3. 输出新增missingInformation要检查哪里？共享输出Schema、模型提示词、前端读取展示和相关验证；具体独立修改在本单元综合任务实施。

当前仅要求学生完成Controller局部修改并解释请求路径；下一步从浏览器验证合法输入、数字输入与空白输入。当前独立接口尚未验收，D03整体仍进行中。

官方资料：https://docs.nestjs.com/controllers 、 https://docs.nestjs.com/providers

教师验证：学生structured-chain.ts语法转换通过；局部处理逻辑配模拟Service验证3类非法输入抛400且业务调用0次、合法输入调用1次、空格字符串现有规则通过。HTTP端点未启动验收，联网模型请求0次；学生Controller修改与浏览器结果待交。
