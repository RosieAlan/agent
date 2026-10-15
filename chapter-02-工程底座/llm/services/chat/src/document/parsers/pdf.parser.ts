import { readFile } from 'node:fs/promises';
import { PDFParse } from 'pdf-parse';

export async function parsePdf(filePath: string): Promise<string> {
  const buffer = await readFile(filePath);
  const parser = new PDFParse({ data: buffer });
  const result = await parser.getText();
  return result.text;
}
