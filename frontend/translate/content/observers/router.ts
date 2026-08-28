/* ============================================================
   Router Observer — 拦截 SPA 路由变化
   ============================================================ */

let onRouteChange: (() => void) | null = null;
let lastUrl = '';

export function initRouterObserver(callback: () => void): void {
  onRouteChange = callback;
  lastUrl = location.href;

  // 拦截 pushState
  const origPush = history.pushState;
  history.pushState = function (...args) {
    origPush.apply(this, args);
    checkUrlChange();
  };

  // 拦截 replaceState
  const origReplace = history.replaceState;
  history.replaceState = function (...args) {
    origReplace.apply(this, args);
    checkUrlChange();
  };

  // 监听 popstate
  window.addEventListener('popstate', checkUrlChange);

  // 监听 hashchange
  window.addEventListener('hashchange', checkUrlChange);
}

function checkUrlChange(): void {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    // 延迟触发，等待新页面 DOM 加载
    setTimeout(() => {
      onRouteChange?.();
    }, 500);
  }
}

export function stopRouterObserver(): void {
  onRouteChange = null;
}
