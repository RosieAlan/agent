# D03第三块：模板链返回结构化对象

对应原课程3.7.1–3.7.3。前置证据：D01 Schema/withStructuredOutput实作与D03模板、文本链真实运行。目标：会定义课程原版action/constraints/entities，解释describe与类型推导，把模板接到结构化模型，读取对象字段并定位失败。后续本单元继续共享contracts和NestJS接口；当前为独立脚本练习。

## 先把结果形状写清楚

课程三个字段分别为action:string、constraints:string[]、entities:string[]。注册需求的参考结果为action="用户注册"，constraints=["注册时必须绑定手机号","密码至少8位"]，entities=["用户","手机号","密码"]。具体措辞允许变化，原文依据和字段类型必须正确。

z来自Zod，z.object定义对象字段；z.string定义字符串；z.array(z.string())定义字符串数组。字段默认必填。describe接收文字描述并返回带描述的Schema，帮助模型理解字段用途；它仍按对应类型校验，动作是否准确、内容是否有原文依据要另做业务检查。空字符串也满足z.string；至少一项数组等要求需要专门规则，当前按缺失时空值处理。

z.infer<typeof RequirementResultSchema>从Schema推导TypeScript类型，方便编辑器提示和编译检查。Schema承担运行时检查，TypeScript类型服务开发时检查。

## 三行组合代码的执行时机

model.withStructuredOutput(RequirementResultSchema)创建带结构定义、结果解析和校验的可调用组件；创建时配置行为。prompt.pipe(structuredModel)创建组合后的调用链。await chain.invoke({audience,input})执行模板填充和模型请求，成功时返回校验后的对象。

输入变量对象 → 填好消息的PromptValue → 结构化模型调用及解析校验 → RequirementResult对象。模型底层仍返回消息，结构化封装处理消息后给调用方对象。前一块StringOutputParser链的终点是字符串，本块结构化链的终点是对象。

## 学生完整文件

学生创建interview-training/labs/w1-d3/structured-chain.ts。保留已有chain-call.ts方便对比。为保证当前练习独立可运行，Schema暂写在同文件；原课程共享contracts方案在本单元接口部分继续落实。下列import复用当前已安装依赖与模型工厂。

```ts
import '../../../chapter-02-工程底座/llm/services/chat/src/load-env.js';
import { createChatModel } from '../../../chapter-02-工程底座/llm/services/chat/src/llm/model.factory.js';
import { ChatPromptTemplate } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/dist/prompts/index.js';
import { z } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/zod/index.js';

const RequirementResultSchema = z.object({
  action: z.string().describe('原文的核心动作，使用动词加对象概括'),
  constraints: z.array(z.string()).describe('原文明确提出的限制条件'),
  entities: z.array(z.string()).describe('原文涉及的人或事物名称'),
});

type RequirementResult = z.infer<typeof RequirementResultSchema>;

async function main() {
  const input = process.argv[2] ?? '用户注册时必须绑定手机号，密码至少8位。';
  const prompt = ChatPromptTemplate.fromMessages([
    ['system', `你是需求结构化抽取助手，结果面向{audience}。
提取核心动作、明确约束、涉及对象。
事实以用户原文为依据，明确约束只记录原文已经说明的内容。
尚未说明的短信验证码、手机号格式、密码复杂度等保留为未知。
缺少核心动作时action填空字符串；缺少约束或对象时对应数组填空数组。`],
    ['human', '请整理以下需求：\n{input}'],
  ]);

  const model = createChatModel();
  const structuredModel = model.withStructuredOutput(RequirementResultSchema);
  const chain = prompt.pipe(structuredModel);

  const result: RequirementResult = await chain.invoke({
    audience: '产品经理',
    input,
  });

  console.log('完整结果：\n', JSON.stringify(result, null, 2));
  console.log('核心动作：', result.action);
  console.log('约束数量：', result.constraints.length);
  console.log('约束是数组：', Array.isArray(result.constraints));
}

main().catch((error: unknown) => {
  console.error('结构化调用失败：', error instanceof Error ? error.name : '未知错误');
  process.exitCode = 1;
});
```

运行一次脚本执行一次链调用，SDK自身重试可能增加实际请求次数；供应商支持情况与超时等问题按实际错误处理。教师验证使用本地固定响应，真实模型调用由学生运行。

```powershell
cd 'C:\Users\Administrator\Desktop\newAgent\agent-course\chapter-02-工程底座\llm\services\chat'
bun run '../../../../interview-training/labs/w1-d3/structured-chain.ts'
```

从services/chat执行，因为现有模型工厂按工作目录读取配置。预期可直接读取result.action、result.constraints.length，Array.isArray(result.constraints)为true。JSON.stringify只服务终端展示，result仍为对象；未来HTTP接口会把对象序列化为JSON发送给前端。

## 失败与事实核对

- 请求失败：密钥、权限、限流或超时等问题，进入catch，设置失败退出码。
- 响应解析/结构校验失败：封装抛错，进入catch；错误类别和包装方式以供应商/SDK实际实现为准。
- 格式通过、内容偏离原文：例如密码至少6位，Schema仍可通过；应核对原文，标记失败并修正。

withStructuredOutput的支持方式取决于模型与接口能力；当前复用D01已经运行的模型工厂和默认方式。后续接口部分补输入验证和错误响应，D04补超时/受控重试。

## 必背与面试答案

1. ChatPromptTemplate负责把变量填入有角色的消息模板；pipe把可调用步骤串起来；withStructuredOutput为模型调用加入输出结构、解析和校验，成功返回可按字段读取的对象。
2. Schema检查字段和类型，业务检查判断内容是否符合原文；两者共同保证结果可用。describe说明字段含义，类型规则决定格式检查。
3. z.infer从Zod Schema推导TypeScript类型；TypeScript提供开发时检查，Zod在程序运行时检查实际数据。

面试追问：Prompt要求JSON后为什么还校验？模型输出仍有格式、类型或缺字段风险，运行时校验用于拦截这些异常。结构正确就能落库吗？还应做业务依据检查、权限检查与必要的输入验证。

## 作业与下一步

主实作：学生复制完整文件运行，提交完整结果、约束数量及数组检查。合并检查：说明result.constraints由何处规定为数组；密码6位为什么可能通过Schema。答案：z.array(z.string())规定数组元素为字符串；6位属于字符串内容的事实偏差，需要对照原文8位检查。

独立修改在D03综合练习合并：新增待确认事项字段并保持原字段正确，具体要求待接口教学后布置。本块授课/教师离线检查与学生真实运行分别登记；D03接口、综合修改与排错尚待完成。

官方参考：https://docs.langchain.com/oss/javascript/integrations/chat/openai

教师验证：讲义TypeScript语法转换通过；当前本地ChatOpenAI结构化封装配固定响应验证对象返回及错误类型拦截，另验证事实偏差可通过Schema，共4项通过；固定响应2次、联网模型请求0次。学生真实运行待交。
