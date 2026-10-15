import { readFile } from 'node:fs/promises';

export async function parseText(filePath: string): Promise<string> {
  return readFile(filePath, 'utf8');
}
