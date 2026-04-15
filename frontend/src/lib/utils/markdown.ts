import { marked } from 'marked';
import DOMPurify from 'dompurify';

export async function renderMarkdown(md: string): Promise<string> {
	const raw = await marked(md);
	return DOMPurify.sanitize(raw);
}
