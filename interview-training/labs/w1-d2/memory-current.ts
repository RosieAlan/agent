import "../../../chapter-02-工程底座/llm/services/chat/src/load-env.js";
import { createChatModel } from "../../../chapter-02-工程底座/llm/services/chat/src/llm/model.factory.js";
import { createAgent } from "../../../chapter-02-工程底座/llm/services/chat/node_modules/langchain/dist/index.js";
import { MemorySaver } from "../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/langgraph/dist/index.js";

async function main() {
  const model = createChatModel();
  const checkpointer = new MemorySaver();

  const agent = createAgent({
    model,
    tools: [],
    systemPrompt:
      "根据当前会话提供的信息回答。需求单号未知时明确说未知。简短回答。",
    checkpointer,
  });

  const configA = {
    configurable: { thread_id: "a" },
  };

  const configB = {
    configurable: { thread_id: "b" },
  };

  const first = await agent.invoke(
    {
      messages: [
        {
          role: "user",
          content:
            "需求单号是REQ-2026-001，我们要做一个需求分析助手。",
        },
      ],
    },
    configA,
  );
  console.log("A第一轮：", first.messages.at(-1)?.content);

  const second = await agent.invoke(
    {
      messages: [
        { role: "user", content: "刚才的需求单号是什么？" },
      ],
    },
    configA,
  );
  console.log("A第二轮：", second.messages.at(-1)?.content);

  const other = await agent.invoke(
    {
      messages: [
        { role: "user", content: "当前会话的需求单号是什么？" },
      ],
    },
    configB,
  );
  console.log("B第一轮：", other.messages.at(-1)?.content);

  const savedA = await agent.getState(configA);
  const savedB = await agent.getState(configB);

  console.log("A历史条数：", savedA.values.messages.length);
  console.log("B历史条数：", savedB.values.messages.length);
}

main().catch((error: unknown) => {
  console.error(
    "运行失败：",
    error instanceof Error ? error.name : "未知错误",
  );
  process.exitCode = 1;
});