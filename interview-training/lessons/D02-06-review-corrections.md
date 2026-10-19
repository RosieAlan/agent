# D02综合批改：对象生命周期、条件版本、提问检查

2026-10-19。衔接原4.1需求澄清、4.2会话记忆和D01 Schema。原课程完整范围继续按既定单元覆盖。

## 学生回答与状态

1. 学生指出每次请求新建MemorySaver会出问题，方向正确；复用进程内对象与数据库持久化的区别、同会话thread_id保持一致待复述。
2. 学生答确认值60天、确认后90天、删除旧条件。原题初始值30天；提议阶段当前已确认值30天，待确认提议90天；明确同意后当前值90天，原始历史保留修改过程。此题待复测。
3. 学生明确表示提问检查不懂，补讲数量校验与业务事实检查，待独立回答。

## 对象复用与持久化

服务启动时创建MemorySaver和agent，由后续请求复用；相同会话采用相同thread_id。这个方案在同一进程内延续历史。数据库checkpointer把状态保存到持久存储，用于跨服务重启恢复；后续数据库检查点单元完整实作。

## 条件更新

| 用户说的话 | 当前已确认值 | 待确认提议 | 完整记录 |
|---|---:|---:|---|
| 已确认保存30天 | 30 | 无 | 保留原话 |
| 要不要改成90天 | 30 | 90 | 追加讨论 |
| 确定改成90天 | 90 | 清除该待确认项 | 追加确认，保留此前原话 |

这使报告采用最新确认值，历史仍可追溯变化来源。历史删除需按用户删除要求、保留策略等另行处理。

## 数量校验与事实检查

Prompt约定最多3个待确认问题；Zod数组.max(3)对返回数量做程序校验。parse在检查通过时返回数据，在失败时抛出ZodError；超数量可捕获错误后要求模型限次重选或提供明确降级。

```ts
import { z } from 'zod';

const AnswerSchema = z.object({
  questions: z.array(z.object({
    field: z.string(),
    text: z.string(),
  })).max(3),
});

const confirmed = { historyRetentionDays: 30 };
const candidate = {
  questions: [
    { field: 'historyRetentionDays', text: '聊天记录保存多少天？' },
  ],
};

const checked = AnswerSchema.parse(candidate);
const pending = checked.questions.filter(
  question => !Object.hasOwn(confirmed, question.field),
);
```

field标明问题对应哪个需求字段，text保存展示给用户的问题。Object.hasOwn检查当前已确认对象是否含对应字段。本例该字段已确认，因此pending为空，保留原始candidate和checked便于排查。

上述代码适用于“询问缺失字段”的明确场景。完整系统需使用约定字段名，校验问题文本与字段的对应关系，并区分缺失值、确认已有值、提议修改和冲突澄清。数量检查通过后，业务内容仍需与当前条件和原始用户依据核对。与已确认30天存在冲突时，应询问具体冲突；泛泛询问保存期限会重复已有信息。

## 必背答案

Prompt描述期望行为；Schema检查结构、类型和数量；业务检查将输出与已确认条件及用户原话对照。检查失败后进入明确的修正或降级分支，确认通过的数据才交给前端展示或下游处理。

## 教师检查与独立检查

使用项目已安装Zod离线检查：5个问题被.max(3)拒绝；已确认保存期限对应的问题从pending排除；原始结果仍保留。供应商请求0次，临时文件0个。参考：[Zod数组校验](https://zod.dev/api#arrays)。

学生集中复答：①服务进程内如何创建与复用MemorySaver，同会话thread_id怎样保持；②提议90天及确认90天两个时刻的当前值和历史；③3个问题的Schema通过后，仍询问已确认期限，应检查什么。当前D02继续，整体完整通过1/32。

## 完整功能阅读：模型输出到待确认问题

2026-10-19续课。以下为纯函数阅读片段，candidate代表模型返回的候选对象，confirmed只存当前有效且已确认的字段。Zod枚举约束field的可选名称；safeParse返回success及data或error；filter返回筛选后的新数组。代码放在收到模型输出之后、向前端返回问题之前。模型调用、数据库和页面由对应课程继续实作。

```ts
const AnswerSchema = z.object({
  questions: z.array(z.object({
    field: z.enum([
      'historyRetentionDays',
      'reportFormat',
      'notificationChannel',
    ]),
    text: z.string(),
  })).max(3),
});

// JavaScript阅读片段，z来自本讲已有的Zod导入。
function prepareQuestions(candidate, confirmed) {
  const parsed = AnswerSchema.safeParse(candidate);
  if (!parsed.success) {
    return { status: 'invalid_output', issues: parsed.error.issues };
  }
  return {
    status: 'ready',
    questions: parsed.data.questions.filter(
      question => !Object.hasOwn(confirmed, question.field),
    ),
  };
}
```

原始三条问题分别询问保存期限、报告格式、通知渠道。confirmed只有保存期限30天时，返回报告格式和通知渠道两条问题。若本次用户另外确认报告格式为Markdown，应把该字段加入confirmed，再次筛选得到通知渠道一条。完整原始对话继续追加保存。实际系统仍需检查text与field语义对应、提问优先级和明确修改/冲突确认；此函数仅完成结构/数量与缺失字段过滤。

格式失败返回invalid_output，调用方进入限次修正或明确错误提示；ready时才展示questions。空问题数组表示本例列出的字段已经有答案，完整需求是否足够仍由业务必填规则判断。

教师离线四项检查通过：确认字段过滤、加入报告格式后的筛选、四条问题数量失败、questions类型错误；供应商请求0次，临时文件0个。

集中独立检查：①在已确认保存30天、报告格式Markdown时，三条候选问题最终留下哪条，模型提议永久保存应写在哪里；②第一轮thread_id=a、第二轮thread_id=b时的历史问题，以及MemorySaver创建/复用位置；③假设总容量10000、输出2000、余量500、其他输入1500，历史预算多少。参考答案分别为通知渠道/待确认、同一会话保持同一编号且服务持续复用对象、6000。学生需要独立说明依据，当前仍待作答。
