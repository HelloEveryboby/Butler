/**
 * Dynamic Style and Theme Injection Manager in TypeScript
 */

import { appConfig } from './config';

export type ThemeName = 'win11' | 'win11-dark';

export class StyleManager {
  private styleElement: HTMLStyleElement | null = null;

  constructor() {
    this.ensureStyleElement();
    this.applyTheme();
  }

  private ensureStyleElement(): void {
    if (typeof document === 'undefined') return;
    let el = document.getElementById('butler-dynamic-styles') as HTMLStyleElement;
    if (!el) {
      el = document.createElement('style');
      el.id = 'butler-dynamic-styles';
      document.head.appendChild(el);
    }
    this.styleElement = el;
  }

  public injectBaseStyles(): void {
    if (!this.styleElement) return;

    const blurVal = appConfig.get('blurAmount') || 20;
    const fontFam = appConfig.get('fontFamily') || '"Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei", sans-serif';
    const fontSize = appConfig.get('fontSize') || '14px';

    const cssRules = `
      :root {
        --glass-blur: ${blurVal}px;
        --glass-saturation: 150%;
        --apple-easing: cubic-bezier(0.2, 0, 0, 1);
        --font-family: ${fontFam};
        --font-size: ${fontSize};
        --subpixel-border: 1px solid var(--border-color);
      }

      body {
        font-family: var(--font-family);
        font-size: var(--font-size);
        transition: background 0.3s var(--apple-easing);
      }

      /* Win11 快速指令浮窗 */
      .flash-container {
        position: relative;
        width: 90%;
        max-width: 600px;
        background: var(--win11-mica, rgba(255, 255, 255, 0.72));
        backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturation));
        -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturation));
        border: 1px solid var(--border-strong);
        border-radius: 8px;
        box-shadow: 0 16px 48px rgba(0, 0, 0, 0.28);
        padding: 12px;
        display: flex;
        align-items: center;
        gap: 10px;
        animation: slideIn 0.18s var(--apple-easing);
      }

      @keyframes slideIn {
        from { transform: translateY(-12px) scale(0.99); opacity: 0; }
        to { transform: translateY(0) scale(1); opacity: 1; }
      }

      .input-box {
        flex: 1;
        background: var(--surface, #fbfbfb);
        border: 1px solid var(--border-strong);
        outline: none;
        color: var(--text-primary, #1b1b1b);
        font-size: 15px;
        padding: 9px 14px;
        border-radius: 4px;
        transition: border-color 0.15s var(--apple-easing), box-shadow 0.15s var(--apple-easing);
      }

      .input-box:focus {
        background: var(--surface, #fbfbfb);
        border-color: var(--accent-color, #0078d4);
        box-shadow: inset 0 -2px 0 var(--accent-color, #0078d4);
      }

      .input-box::placeholder {
        color: var(--text-secondary, #5f5f5f);
      }

      .hint {
        position: absolute;
        bottom: -28px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 12px;
        color: var(--text-secondary, #5f5f5f);
        white-space: nowrap;
        text-shadow: 0 1px 2px rgba(255, 255, 255, 0.5);
      }

      .mic-button {
        width: 38px;
        height: 38px;
        border-radius: 4px;
        background: var(--accent-soft, rgba(0, 120, 212, 0.1));
        border: 1px solid var(--border-color, #e2e2e2);
        color: var(--accent-color, #0078d4);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.15s var(--apple-easing);
      }

      .mic-button:hover {
        background: var(--surface-2, #f0f0f0);
        border-color: var(--border-strong);
      }

      .mic-button.active {
        background: var(--danger, #c42b1c);
        border-color: var(--danger, #c42b1c);
        color: #ffffff;
        box-shadow: none;
        animation: pulseMic 1.5s infinite;
      }

      @keyframes pulseMic {
        0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(196, 43, 28, 0.5); }
        70% { transform: scale(1.05); box-shadow: 0 0 0 10px rgba(196, 43, 28, 0); }
        100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(196, 43, 28, 0); }
      }

      .voice-canvas-overlay {
        position: absolute;
        top: -100px;
        left: 50%;
        transform: translateX(-50%);
        width: 200px;
        height: 100px;
        pointer-events: none;
      }

      .voice-status-badge {
        font-size: 12px;
        padding: 4px 10px;
        border-radius: 4px;
        background: var(--surface-2, #f0f0f0);
        border: 1px solid var(--border-color, #e2e2e2);
        color: var(--text-secondary, #5f5f5f);
        white-space: nowrap;
      }
    `;

    this.styleElement.textContent = cssRules;
  }

  public applyTheme(themeName?: ThemeName): void {
    const theme: ThemeName = themeName === 'win11-dark' ? 'win11-dark' : 'win11';
    document.body.classList.remove('theme-win11', 'theme-win11-dark', 'theme-apple', 'theme-dark', 'theme-google');
    document.body.classList.add(`theme-${theme}`);
    document.body.dataset.theme = theme;
    this.injectBaseStyles();
  }
}

export const styleManager = new StyleManager();

if (typeof window !== 'undefined') {
  (window as any).setTheme = (theme: ThemeName): void => styleManager.applyTheme(theme);
}
