import { readFile } from 'node:fs/promises';
import * as mammoth from 'mammoth';

export async function parseDocx(filePath: string): Promise<string> {
  const buffer = await readFile(filePath);
  const result = await mammoth.extractRawText({ buffer });
  return result.value;
}
