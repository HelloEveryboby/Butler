/**
 * 安全工具集
 *
 * 集中管理所有安全相关的工具函数。
 * 输入验证、路径净化、速率限制等。
 */

/**
 * 命令最大长度
 */
const MAX_COMMAND_LENGTH = 10000;

/**
 * 命令速率限制 (防止暴力发送)
 */
const RATE_LIMIT_WINDOW_MS = 1000; // 1 秒
const RATE_LIMIT_MAX = 5; // 每窗口最多 5 条

const rateLimitLog: number[] = [];

/**
 * 检查速率限制
 * @returns true = 允许, false = 被限流
 */
export function checkRateLimit(): boolean {
  const now = Date.now();
  // 清理过期记录
  while (rateLimitLog.length > 0 && rateLimitLog[0] < now - RATE_LIMIT_WINDOW_MS) {
    rateLimitLog.shift();
  }
  if (rateLimitLog.length >= RATE_LIMIT_MAX) {
    return false;
  }
  rateLimitLog.push(now);
  return true;
}

/**
 * 验证用户命令输入
 * @returns 验证后的安全字符串，或 null 表示拒绝
 */
export function sanitizeCommand(input: string): string | null {
  if (typeof input !== 'string') return null;

  const trimmed = input.trim();

  // 空命令
  if (trimmed.length === 0) return null;

  // 长度限制
  if (trimmed.length > MAX_COMMAND_LENGTH) {
    console.warn('[Security] Command exceeds max length');
    return null;
  }

  // 控制字符过滤 (保留换行和制表)
  // eslint-disable-next-line no-control-regex
  if (/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(trimmed)) {
    console.warn('[Security] Command contains forbidden control characters');
    return null;
  }

  return trimmed;
}

/**
 * 验证文件路径
 * @returns true = 安全, false = 拒绝
 */
export function isValidFilePath(path: string): boolean {
  if (typeof path !== 'string' || path.length === 0) return false;

  // 禁止路径遍历
  if (path.includes('..')) return false;

  // 禁止特殊字符
  if (/[<>"'|?*\x00-\x1f]/.test(path)) return false;

  // 禁止绝对路径到敏感目录
  const lower = path.toLowerCase();
  const blocked = [
    '/etc/',
    '/proc/',
    '/sys/',
    'c:\\windows',
    'c:\\users\\all users',
    '~/.ssh',
    '~/.aws',
  ];
  for (const b of blocked) {
    if (lower.startsWith(b) || lower.includes('/' + b)) return false;
  }

  return true;
}

/**
 * 验证技能名称 (只允许安全字符)
 */
export function isValidSkillName(name: string): boolean {
  return /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name);
}

/**
 * 验证方法名称 (只允许安全字符)
 */
export function isValidMethodName(name: string): boolean {
  return /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name);
}

/**
 * 生成随机 nonce (用于 CSP)
 */
export function generateNonce(): string {
  const array = new Uint8Array(16);
  crypto.getRandomValues(array);
  return btoa(String.fromCharCode(...array));
}

/**
 * localStorage 安全封装
 * - 捕获 quota exceeded 错误
 * - 自动 JSON 序列化/反序列化
 */
export const safeStorage = {
  get<T>(key: string, fallback: T): T {
    try {
      const raw = localStorage.getItem(key);
      if (raw === null) return fallback;
      return JSON.parse(raw) as T;
    } catch {
      return fallback;
    }
  },

  set(key: string, value: unknown): boolean {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (err) {
      console.error('[Security] localStorage.setItem failed:', err);
      return false;
    }
  },

  remove(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch {
      // ignore
    }
  },
};
