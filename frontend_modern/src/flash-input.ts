/**
 * 浮窗入口 (flash_input.html)
 *
 * Alt+Space 快捷浮窗的独立入口脚本。
 */

import { bridge } from '@/api';
import { sanitizeCommand, checkRateLimit } from '@/utils/security';
import { initErrorBoundary } from '@/utils/error-boundary';

initErrorBoundary();

const input = document.getElementById('main-input') as HTMLInputElement;

input?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const raw = input.value.trim();
    const safe = sanitizeCommand(raw);
    if (!safe) return;

    if (!checkRateLimit()) {
      console.warn('[Flash] Rate limited');
      return;
    }

    bridge.submitFlashCommand(safe);
    input.value = '';
  } else if (e.key === 'Escape') {
    bridge.hideFlash();
  }
});

// pywebview 就绪后聚焦
window.addEventListener('pywebviewready', () => {
  input?.focus();
});
