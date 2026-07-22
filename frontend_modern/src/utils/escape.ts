/**
 * HTML 转义工具
 * 防止 XSS 注入，替代原来的 window.escapeHTML
 */

const ESCAPE_MAP: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#039;',
};

const ESCAPE_RE = /[&<>"']/g;

/**
 * 转义 HTML 特殊字符
 */
export function escapeHTML(str: string | null | undefined): string {
  if (str === null || str === undefined) return '';
  return String(str).replace(ESCAPE_RE, (char) => ESCAPE_MAP[char]);
}

/**
 * 反转义 HTML 实体
 */
export function unescapeHTML(str: string): string {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'");
}
