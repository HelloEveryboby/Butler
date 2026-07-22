/**
 * Butler Toast 通知系统
 * 替代原来的 window.showToast
 *
 * 安全措施:
 * - title 和 message 通过 escapeHTML 转义后渲染
 * - 不使用 innerHTML 插入用户可控内容
 */

import { escapeHTML } from '@/utils/escape';

type ToastType = 'success' | 'error' | 'warning' | 'info';

const ICONS: Record<ToastType, string> = {
  success: '✅',
  error: '❌',
  warning: '⚠️',
  info: 'ℹ️',
};

class ToastManager {
  private container: HTMLElement | null = null;

  private ensureContainer(): HTMLElement {
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.className = 'toast-container';
      this.container.setAttribute('role', 'log');
      this.container.setAttribute('aria-live', 'polite');
      document.body.appendChild(this.container);
    }
    return this.container;
  }

  /**
   * 显示 Toast 通知
   */
  show(title: string, message: string, type: ToastType = 'info', duration = 4000): void {
    const container = this.ensureContainer();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.setAttribute('role', 'status');

    // 使用 DOM API 而非 innerHTML，防止 XSS
    const icon = document.createElement('span');
    icon.className = 'toast-icon';
    icon.textContent = ICONS[type];

    const content = document.createElement('div');
    content.className = 'toast-content';

    const titleEl = document.createElement('div');
    titleEl.className = 'toast-title';
    titleEl.textContent = title; // textContent 自动转义

    const msgEl = document.createElement('div');
    msgEl.className = 'toast-message';
    msgEl.textContent = message;

    content.appendChild(titleEl);
    content.appendChild(msgEl);
    toast.appendChild(icon);
    toast.appendChild(content);
    container.appendChild(toast);

    // 自动关闭
    setTimeout(() => {
      toast.classList.add('leaving');
      toast.addEventListener('animationend', () => {
        toast.remove();
        if (container.children.length === 0) {
          container.remove();
          this.container = null;
        }
      });
    }, duration);
  }

  success(title: string, message: string): void {
    this.show(title, message, 'success');
  }

  error(title: string, message: string): void {
    this.show(title, message, 'error', 6000);
  }

  warning(title: string, message: string): void {
    this.show(title, message, 'warning', 5000);
  }

  info(title: string, message: string): void {
    this.show(title, message, 'info');
  }
}

/** 全局单例 */
export const toast = new ToastManager();

// 向后兼容: 暴露到 window
if (typeof window !== 'undefined') {
  window.showToast = (title: string, message: string, type?: string) => {
    toast.show(title, message, (type as ToastType) || 'info');
  };
}
