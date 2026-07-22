import type { ButlerBridge } from './bridge';
import { NativeBridge } from './bridge-native';
import { WebBridge } from './bridge-web';

/**
 * 自动检测运行环境并选择合适的桥接实现
 *
 * - pywebview 环境 → NativeBridge (调用 Python 后端)
 * - 浏览器环境 → WebBridge (mock，支持独立开发)
 */
function isPywebview(): boolean {
  return !!(window as any).pywebview?.api;
}

export const bridge: ButlerBridge = isPywebview() ? new NativeBridge() : new WebBridge();

// 开发环境下输出桥接类型
if (import.meta.env.DEV) {
  console.warn(
    `[Butler Bridge] 使用 ${isPywebview() ? 'NativeBridge (pywebview)' : 'WebBridge (浏览器调试)'}`,
  );
}

export type { ButlerBridge };
