import fs from 'node:fs';
import path from 'node:path';
import { Injectable } from '@nestjs/common';
import {
  HumanMessage,
  ToolMessage,
  type BaseMessage,
} from '@langchain/core/messages';
import type { StructuredToolInterface } from '@langchain/core/tools';
import { createChatModel } from '../model.factory.js';
import {
  queryRequirementTool,
  readFileTool,
  safePath,
  writeFileTool,
} from '../tools/business.tools.js';

@Injectable()
export class FilesystemService {
  private tools: StructuredToolInterface[] = [
    queryRequirementTool,
    readFileTool,
    writeFileTool,
  ];
  private toolMap = new Map(
    this.tools.map((t) => [t.name, t] as const),
  );
  private model = createChatModel().bindTools(this.tools);

  async chat(input: string) {
    const messages: BaseMessage[] = [new HumanMessage(input)];
    const usedTools: string[] = [];

    for (let i = 0; i < 5; i++) {
      const ai = await this.model.invoke(messages);
      messages.push(ai);

      const calls = ai.tool_calls ?? [];
      if (calls.length === 0) {
        return { response: ai.text, usedTools };
      }

      for (const call of calls) {
        usedTools.push(call.name);
        const selected = this.toolMap.get(call.name);
        let result: unknown;
        try {
          result = selected
            ? await selected.invoke(call.args)
            : { error: `未知工具 ${call.name}` };
        } catch (error) {
          result = { error: (error as Error).message };
        }
        messages.push(
          new ToolMessage({
            content: JSON.stringify(result),
            tool_call_id: call.id ?? call.name,
          }),
        );
      }
    }
    return { response: '工具调用超出上限', usedTools };
  }

  writeReport(filePath: string, content: string) {
    const full = safePath(filePath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf8');
    return filePath;
  }
}
