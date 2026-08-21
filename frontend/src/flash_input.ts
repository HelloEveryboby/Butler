/**
 * Butler Flash Input Script in TypeScript
 */

function initFlashInput(): void {
  const input = document.getElementById('main-input') as HTMLInputElement;
  if (!input) return;

  input.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      const val = input.value.trim();
      if (val && window.pywebview?.api) {
        window.pywebview.api.submit_flash_command(val);
        input.value = '';
      }
    } else if (e.key === 'Escape') {
      if (window.pywebview?.api) {
        window.pywebview.api.hide_flash();
      }
    }
  });

  window.addEventListener('pywebviewready', () => {
    input.focus();
  });
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    initFlashInput();
  });
}
