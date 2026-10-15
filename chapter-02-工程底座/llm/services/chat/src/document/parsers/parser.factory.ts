import { parseDocx } from './docx.parser.js';
import { parsePdf } from './pdf.parser.js';
import { parseText } from './text.parser.js';

export async function extractText(
  filePath: string,
  mimeType: string,
): Promise<string> {
  switch (mimeType) {
    case 'application/pdf':
      return parsePdf(filePath);
    case 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
    case 'application/msword':
      return parseDocx(filePath);
    case 'text/plain':
    case 'text/markdown':
    case 'text/x-markdown':
    default:
      return parseText(filePath);
  }
}
