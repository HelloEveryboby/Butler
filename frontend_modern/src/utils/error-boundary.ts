/**
 * 错误边界 (Error Boundary)
 *
 * 全局未捕获错误处理，防止应用白屏。
 * 捕获错误后显示友好提示，不影响其他模块运行。
 */

import { toast } from '@/utils/toast';

interface ErrorInfo {
  message: string;
  source?: string;
  lineno?: number;
  colno?: number;
  error?: Error;
}

/**
 * 初始化全局错误边界
 *
 * 在 main.ts 中最先调用，确保后续所有错误都能被捕获。
 */
export function initErrorBoundary(): void {
  // 捕获同步未处理错误
  window.addEventListener('error', (event: ErrorEvent) => {
    const info: ErrorInfo = {
      message: event.message,
      source: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      error: event.error,
    };
    handleError(info);
    // 不阻止默认行为，让浏览器控制台也能看到
  });

  // 捕获 Promise 未处理 rejection
  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
    const reason = event.reason;
    const info: ErrorInfo = {
      message: reason instanceof Error ? reason.message : String(reason),
      error: reason instanceof Error ? reason : undefined,
    };
    handleError(info);
    // 阻止默认的 console.error 输出 (已手动处理)
    event.preventDefault();
  });

  console.warn('[ErrorBoundary] Global error boundary initialized');
}

/**
 * 统一错误处理
 */
function handleError(info: ErrorInfo): void {
  // 过滤掉 pywebview 未就绪的正常警告
  if (info.message?.includes('pywebview')) {
    return;
  }

  // 过滤掉浏览器扩展注入的错误
  if (info.source && !info.source.startsWith(location.origin) && !info.source.startsWith('http')) {
    return;
  }

  // 开发环境下详细输出
  if (import.meta.env.DEV) {
    console.group('[ErrorBoundary] Caught error');
    console.error('Message:', info.message);
    if (info.source) console.error('Source:', info.source, 'Line:', info.lineno);
    if (info.error) console.error('Stack:', info.error.stack);
    console.groupEnd();
  }

  // 生产环境下静默记录，不打扰用户
  // 只有严重错误才显示 toast
  if (isCriticalError(info)) {
    toast.error('系统异常', '发生了意外错误，请刷新页面重试。');
  }
}

/**
 * 判断是否为严重错误 (需要用户关注)
 */
function isCriticalError(info: ErrorInfo): boolean {
  const msg = info.message?.toLowerCase() || '';

  // 网络错误通常不严重
  if (msg.includes('network') || msg.includes('fetch')) return false;

  // 资源加载失败不严重
  if (msg.includes('loading') || msg.includes('script')) return false;

  return true;
}

/**
 * 包装异步函数，捕获错误并返回 fallback
 */
export function withErrorBoundary<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  return fn().catch((err) => {
    handleError({ message: err?.message || 'Unknown error', error: err });
    return fallback;
  });
}

/**
 * 包装同步函数，捕获错误并返回 fallback
 */
export function withSyncErrorBoundary<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch (err: any) {
    handleError({ message: err?.message || 'Unknown error', error: err });
    return fallback;
  }
}
