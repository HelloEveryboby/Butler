/**
 * 旧浮层（终端 / 备忘录 / 设置）窗口装饰：
 * 把 macOS 红黄绿圆点替换为 Win11 标题栏按钮布局，并挂接最小化 / 最大化行为。
 */

export function decorateOverlays(): void {
  document.querySelectorAll<HTMLElement>('.overlay-panel').forEach((panel) => {
    panel.classList.add('win11-dialog');
    const header = panel.querySelector<HTMLElement>('.panel-header');
    if (!header) return;

    const controls = header.querySelector<HTMLElement>('.window-controls');
    if (!controls) return;

    // 旧浮层标题栏使用内联样式，这里统一为 Win11 标题栏度量。
    header.style.height = '40px';
    header.style.padding = '0 0 0 16px';
    header.style.margin = '0';
    header.style.borderBottom = '1px solid var(--border-color)';
    header.style.justifyContent = 'space-between';

    header.appendChild(controls);

    header.querySelectorAll<HTMLElement>(':scope > div').forEach((child) => {
      if (child !== controls && !child.textContent?.trim() && child.style.width === '52px') {
        child.remove();
      }
    });

    controls.querySelectorAll<HTMLElement>('.control-dot').forEach((dot) => {
      const isClose = dot.classList.contains('close');
      const isMinimize = dot.classList.contains('minimize');
      const isMaximize = dot.classList.contains('maximize');

      if (isClose) {
        dot.title = '关闭';
        dot.setAttribute('aria-label', '关闭');
        if (!dot.getAttribute('onclick')) {
          dot.addEventListener('click', () => panel.classList.add('hidden'));
        }
      } else if (isMinimize) {
        dot.title = '最小化';
        dot.setAttribute('aria-label', '最小化');
        dot.addEventListener('click', () => panel.classList.add('hidden'));
      } else if (isMaximize) {
        dot.title = '最大化';
        dot.setAttribute('aria-label', '最大化');
        dot.addEventListener('click', () => {
          panel.classList.toggle('win11-maximized');
          panel.classList.toggle('win11-restored');
        });
      }
    });
  });
}
