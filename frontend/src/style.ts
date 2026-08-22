/**
 * Dynamic Style and Theme Injection Manager in TypeScript
 */

import { appConfig } from './config';

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
    const fontFam = appConfig.get('fontFamily') || '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", sans-serif';
    const fontSize = appConfig.get('fontSize') || '14px';

    const cssRules = `
      :root {
        --glass-blur: ${blurVal}px;
        --glass-saturation: 180%;
        --apple-easing: cubic-bezier(0.16, 1, 0.3, 1);
        --font-family: ${fontFam};
        --font-size: ${fontSize};
        --subpixel-border: 0.5px solid rgba(255, 255, 255, 0.15);
      }

      body {
        font-family: var(--font-family);
        font-size: var(--font-size);
        transition: background 0.3s var(--apple-easing);
      }

      /* Flash Input Glass Container & Input Box Styles */
      .flash-container {
        position: relative;
        width: 90%;
        max-width: 600px;
        background: rgba(30, 30, 30, 0.82);
        backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturation));
        -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturation));
        border: var(--subpixel-border);
        border-radius: 16px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8);
        padding: 16px;
        display: flex;
        align-items: center;
        gap: 12px;
        animation: slideIn 0.3s var(--apple-easing);
      }

      @keyframes slideIn {
        from { transform: translateY(-20px) scale(0.98); opacity: 0; }
        to { transform: translateY(0) scale(1); opacity: 1; }
      }

      .input-box {
        flex: 1;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.12);
        outline: none;
        color: #ffffff;
        font-size: 16px;
        padding: 10px 16px;
        border-radius: 12px;
        transition: all 0.2s var(--apple-easing);
      }

      .input-box:focus {
        background: rgba(255, 255, 255, 0.15);
        border-color: rgba(0, 122, 255, 0.6);
        box-shadow: 0 0 10px rgba(0, 122, 255, 0.3);
      }

      .input-box::placeholder {
        color: rgba(255, 255, 255, 0.4);
      }

      .hint {
        position: absolute;
        bottom: -28px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 12px;
        color: rgba(255, 255, 255, 0.6);
        white-space: nowrap;
      }

      .mic-button {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: rgba(0, 122, 255, 0.18);
        border: 1px solid rgba(0, 122, 255, 0.4);
        color: #007aff;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.25s var(--apple-easing);
      }

      .mic-button:hover {
        background: rgba(0, 122, 255, 0.35);
        transform: scale(1.05);
      }

      .mic-button.active {
        background: #ff3b30;
        border-color: #ff3b30;
        color: #ffffff;
        box-shadow: 0 0 16px rgba(255, 59, 48, 0.8);
        animation: pulseMic 1.5s infinite;
      }

      @keyframes pulseMic {
        0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 59, 48, 0.6); }
        70% { transform: scale(1.08); box-shadow: 0 0 0 12px rgba(255, 59, 48, 0); }
        100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 59, 48, 0); }
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
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.12);
        color: rgba(255, 255, 255, 0.85);
        white-space: nowrap;
      }
    `;

    this.styleElement.textContent = cssRules;
  }

  public applyTheme(themeName?: 'apple' | 'dark' | 'google'): void {
    const theme = themeName || appConfig.get('theme');
    document.body.classList.remove('theme-apple', 'theme-dark', 'theme-google');
    document.body.classList.add(`theme-${theme}`);
    this.injectBaseStyles();
  }
}

export const styleManager = new StyleManager();
