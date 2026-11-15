/**
 * Win11 标题栏 —— 应用标识、全局搜索、主题切换、系统设置与窗口按钮。
 */

import { appConfig } from '../config';
import { styleManager, type ThemeName } from '../style';
import { icon } from './icons';

const SVG_MIN = '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M1 5h8"/></svg>';
const SVG_MAX = '<svg viewBox="0 0 10 10" aria-hidden="true"><rect x="1.4" y="1.4" width="7.2" height="7.2" rx="0.6"/></svg>';
const SVG_CLOSE = '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M1.5 1.5l7 7M8.5 1.5l-7 7"/></svg>';

export function renderTitleBar(): string {
  return `
    <header class="win11-titlebar">
      <div class="titlebar-left">
        <div class="app-mark"><span>B</span></div>
        <div class="app-name">
          Butler
          <span class="app-subtitle">本地优先智能管家</span>
        </div>
      </div>

      <div class="titlebar-search">
        ${icon('search', 14)}
        <input id="win11-search" type="text" autocomplete="off" spellcheck="false"
               placeholder="搜索页面或输入指令，回车执行">
        <kbd>Ctrl K</kbd>
      </div>

      <div class="titlebar-tools">
        <button class="tb-btn" id="tb-theme" type="button" title="切换深浅色">${icon('moon', 15)}</button>
        <button class="tb-btn" id="tb-settings" type="button" title="系统设置">${icon('gear', 15)}</button>
        <div class="caption-buttons">
          <button class="caption-btn" type="button" data-window-action="minimize" title="最小化">${SVG_MIN}</button>
          <button class="caption-btn" type="button" data-window-action="maximize" title="最大化">${SVG_MAX}</button>
          <button class="caption-btn close" type="button" data-window-action="close" title="关闭">${SVG_CLOSE}</button>
        </div>
      </div>
    </header>`;
}

function windowAction(action: string): void {
  const api = (window as any).pywebview?.api;
  const fn = api?.window_control;
  if (typeof fn === 'function') {
    try {
      fn(action);
      return;
    } catch (e) {
      console.warn('[Win11] window_control failed:', e);
    }
  }
  if (action === 'close' && !api) {
    window.close();
    return;
  }
  window.showToast?.('窗口控制', '当前为浏览器预览模式，窗口按钮仅在桌面客户端内生效。', 'info');
}

function updateThemeIcon(): void {
  const btn = document.getElementById('tb-theme');
  if (!btn) return;
  const dark = appConfig.get('theme') === 'win11-dark';
  btn.innerHTML = icon(dark ? 'sun' : 'moon', 15);
  btn.title = dark ? '切换到浅色' : '切换到深色';
}

export function bindTitleBar(onNavigate: (routeId: string) => void): void {
  const themeBtn = document.getElementById('tb-theme');
  const settingsBtn = document.getElementById('tb-settings');
  const search = document.getElementById('win11-search') as HTMLInputElement | null;

  updateThemeIcon();

  themeBtn?.addEventListener('click', () => {
    const next: ThemeName = appConfig.get('theme') === 'win11-dark' ? 'win11' : 'win11-dark';
    styleManager.applyTheme(next);
    appConfig.set('theme', next);
    updateThemeIcon();
    window.showToast?.('外观', next === 'win11-dark' ? '已切换到 Win11 深色。' : '已切换到 Win11 浅色。', 'success');
  });

  settingsBtn?.addEventListener('click', () => window.toggleSettings?.());

  document.querySelectorAll<HTMLButtonElement>('[data-window-action]').forEach((btn) => {
    btn.addEventListener('click', () => windowAction(btn.dataset.windowAction || ''));
  });

  search?.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      search.blur();
      return;
    }
    if (e.key !== 'Enter') return;
    const query = search.value.trim();
    if (!query) return;
    search.value = '';

    const hit = Array.from(document.querySelectorAll<HTMLElement>('.nav-item[data-route]')).find((item) =>
      (item.textContent || '').toLowerCase().includes(query.toLowerCase())
    );
    if (hit?.dataset.route) {
      onNavigate(hit.dataset.route);
      return;
    }

    onNavigate('chat');
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
      chatInput.innerText = query;
      document.getElementById('send-command-btn')?.click();
    }
  });

  window.addEventListener('keydown', (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      search?.focus();
      search?.select();
    }
  });
}
