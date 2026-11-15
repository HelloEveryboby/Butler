/**
 * Win11 应用外壳 —— 标题栏 + 左侧导航 + 单页内容区。
 */

import { NAV_ITEMS } from './pages';
import { renderAllPages } from './pages';
import { icon } from './icons';
import { bindTitleBar, renderTitleBar } from './TitleBar';
import { Win11Router } from './Router';
import { decorateOverlays } from './overlayChrome';

function renderNav(): string {
  const workItems = NAV_ITEMS.filter((item) => item.group === '工作区')
    .map(
      (item) => `
        <button class="nav-item" type="button" data-route="${item.id}" title="${item.label}">
          <span class="nav-indicator"></span>
          <span class="nav-icon">${icon(item.icon)}</span>
          <span class="nav-label">${item.label}</span>
        </button>`
    )
    .join('');

  return `
    <nav class="win11-nav" aria-label="主导航">
      <div class="nav-group-label">工作区</div>
      ${workItems}
      <div class="nav-spacer"></div>
      <div class="nav-group-label">系统</div>
      <button class="nav-item" type="button" id="nav-settings" title="系统设置">
        <span class="nav-indicator"></span>
        <span class="nav-icon">${icon('gear')}</span>
        <span class="nav-label">系统设置</span>
      </button>
      <div class="nav-foot">
        <span class="nav-status-dot"></span>
        <span>本地服务</span>
      </div>
    </nav>`;
}

export function mountShell(root: HTMLElement): Win11Router {
  root.innerHTML = `
    <div class="win11-shell">
      ${renderTitleBar()}
      <div class="win11-body">
        ${renderNav()}
        <main class="win11-content" id="win11-content">
          ${renderAllPages()}
        </main>
      </div>
    </div>`;

  const router = new Win11Router();
  (window as any).matrix = router;

  bindTitleBar((routeId) => router.navigate(routeId));

  document.getElementById('nav-settings')?.addEventListener('click', () => window.toggleSettings?.());

  decorateOverlays();

  return router;
}
