/* ============================================================
   悬浮球 — 可拖拽，点击翻译/还原，位置记忆
   ============================================================ */

import { TranslateConfig } from '../../utils/types';

let ballEl: HTMLDivElement | null = null;

export function initFloatingBall(
  config: TranslateConfig,
  onToggle: () => void
): void {
  if (ballEl) return;

  ballEl = document.createElement('div');
  ballEl.className = 'bt-floating-ball';
  ballEl.innerHTML = '译';
  ballEl.title = 'Butler Translate (Alt+Q)';

  // 恢复上次位置
  const saved = localStorage.getItem('bt-ball-pos');
  if (saved) {
    try {
      const pos = JSON.parse(saved);
      ballEl.style.right = pos.right || '20px';
      ballEl.style.bottom = pos.bottom || '20px';
    } catch {}
  }

  document.body.appendChild(ballEl);

  // 点击翻译
  ballEl.addEventListener('click', (e) => {
    e.stopPropagation();
    onToggle();
  });

  // 拖拽
  let isDragging = false;
  let startX = 0, startY = 0;
  let startRight = 0, startBottom = 0;

  ballEl.addEventListener('mousedown', (e) => {
    isDragging = false;
    startX = e.clientX;
    startY = e.clientY;
    startRight = parseInt(ballEl!.style.right) || 20;
    startBottom = parseInt(ballEl!.style.bottom) || 20;

    const onMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) isDragging = true;

      ballEl!.style.right = `${Math.max(0, startRight - dx)}px`;
      ballEl!.style.bottom = `${Math.max(0, startBottom - dy)}px`;
    };

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);

      if (isDragging) {
        // 保存位置
        localStorage.setItem('bt-ball-pos', JSON.stringify({
          right: ballEl!.style.right,
          bottom: ballEl!.style.bottom,
        }));
      }
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  });

  // 更新状态
  updateBallState(false);
}

export function updateBallState(translated: boolean): void {
  if (!ballEl) return;
  ballEl.classList.toggle('bt-ball-active', translated);
  ballEl.innerHTML = translated ? '原' : '译';
  ballEl.title = translated ? '显示原文 (Alt+Q)' : '翻译此页面 (Alt+Q)';
}

export function removeFloatingBall(): void {
  ballEl?.remove();
  ballEl = null;
}
