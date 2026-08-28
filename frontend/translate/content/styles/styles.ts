/* ============================================================
   Butler Translate — 样式管理（纯 TS，无 CSS 文件）
   所有样式通过 TypeScript 动态生成并注入到页面
   ============================================================ */

const STYLE_ID = 'butler-translate-styles';

/** 所有样式定义，纯 TS 字符串 */
const STYLES: Record<string, string> = {

  // ---------- 译文容器 ----------
  'bt-translated': `
    position: relative;
    display: block;
    margin: 2px 0 8px 0;
    padding: 4px 8px;
    border-left: 3px solid #4a9eff;
    background: rgba(74, 158, 255, 0.06);
    border-radius: 0 4px 4px 0;
    font-style: normal !important;
    opacity: 0;
    animation: bt-fadeIn 0.3s ease forwards;
  `,

  'bt-translated::before': `
    content: '🌐';
    font-size: 10px;
    margin-right: 4px;
    opacity: 0.5;
  `,

  // ---------- Loading ----------
  'bt-trans-loading': `
    display: inline-block;
    margin-left: 4px;
  `,

  'bt-spinner': `
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid #e0e0e0;
    border-top-color: #4a9eff;
    border-radius: 50%;
    animation: bt-spin 0.6s linear infinite;
    vertical-align: middle;
  `,

  // ---------- 划词翻译气泡 ----------
  'bt-bubble': `
    position: absolute;
    z-index: 2147483647;
    max-width: 360px;
    min-width: 120px;
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    color: #333;
    animation: bt-bubbleIn 0.2s ease;
    pointer-events: auto;
  `,

  'bt-bubble-content': `
    padding: 10px 14px;
    word-break: break-word;
  `,

  'bt-bubble-actions': `
    display: flex;
    justify-content: flex-end;
    gap: 6px;
    padding: 6px 10px;
    border-top: 1px solid #f0f0f0;
  `,

  'bt-bubble-actions button': `
    background: none;
    border: none;
    cursor: pointer;
    font-size: 14px;
    padding: 2px 6px;
    border-radius: 4px;
    color: #666;
  `,

  'bt-bubble-actions button:hover': `
    background: #f0f0f0;
  `,

  'bt-bubble-loading': `
    color: #999;
    font-size: 13px;
  `,

  'bt-error': `
    color: #e74c3c;
    font-size: 13px;
  `,

  // ---------- 悬浮球 ----------
  'bt-floating-ball': `
    position: fixed;
    right: 20px;
    bottom: 20px;
    z-index: 2147483646;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: linear-gradient(135deg, #4a9eff, #1a6dd4);
    color: #fff;
    font-size: 16px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 12px rgba(74, 158, 255, 0.4);
    user-select: none;
    transition: transform 0.2s, box-shadow 0.2s;
  `,

  'bt-floating-ball:hover': `
    transform: scale(1.1);
    box-shadow: 0 4px 20px rgba(74, 158, 255, 0.5);
  `,

  'bt-ball-active': `
    background: linear-gradient(135deg, #e74c3c, #c0392b);
    box-shadow: 0 2px 12px rgba(231, 76, 60, 0.4);
  `,

  // ---------- 剪贴板 Toast ----------
  'bt-clipboard-toast': `
    position: fixed;
    bottom: 80px;
    right: 20px;
    z-index: 2147483647;
    width: 320px;
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    box-shadow: 0 6px 30px rgba(0, 0, 0, 0.15);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
    animation: bt-slideIn 0.3s ease;
  `,

  'bt-clipboard-header': `
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-bottom: 1px solid #f0f0f0;
    font-weight: 600;
    color: #333;
  `,

  'bt-clipboard-header button': `
    background: none;
    border: none;
    cursor: pointer;
    font-size: 16px;
    color: #999;
  `,

  'bt-clipboard-body': `
    padding: 10px 12px;
  `,

  'bt-clipboard-original': `
    color: #999;
    font-size: 12px;
    margin-bottom: 6px;
    max-height: 60px;
    overflow: hidden;
  `,

  'bt-clipboard-translated': `
    color: #333;
    line-height: 1.4;
  `,

  'bt-clipboard-actions': `
    display: flex;
    justify-content: flex-end;
    padding: 6px 12px;
    border-top: 1px solid #f0f0f0;
  `,

  'bt-clipboard-actions button': `
    background: #4a9eff;
    color: #fff;
    border: none;
    padding: 4px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
  `,

  // ---------- 截图翻译 ----------
  'bt-screenshot-overlay': `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 2147483647;
    background: rgba(0, 0, 0, 0.3);
    cursor: crosshair;
  `,

  'bt-screenshot-hint': `
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: #fff;
    font-size: 18px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
    pointer-events: none;
  `,

  'bt-screenshot-selection': `
    position: absolute;
    border: 2px dashed #4a9eff;
    background: rgba(74, 158, 255, 0.1);
  `,

  'bt-screenshot-result': `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 2147483647;
    width: 420px;
    max-height: 500px;
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
    box-shadow: 0 8px 40px rgba(0, 0, 0, 0.2);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    overflow: hidden;
  `,

  'bt-screenshot-result-header': `
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: #f8f9fa;
    border-bottom: 1px solid #e0e0e0;
    cursor: grab;
    font-weight: 600;
    color: #333;
  `,

  'bt-screenshot-result-header button': `
    background: none;
    border: none;
    cursor: pointer;
    font-size: 18px;
    color: #999;
  `,

  'bt-screenshot-result-body': `
    padding: 16px;
    max-height: 300px;
    overflow-y: auto;
  `,

  'bt-screenshot-result-actions': `
    display: flex;
    gap: 8px;
    padding: 10px 16px;
    border-top: 1px solid #f0f0f0;
    justify-content: flex-end;
  `,

  'bt-screenshot-result-actions button': `
    background: #4a9eff;
    color: #fff;
    border: none;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
  `,

  'bt-screenshot-result-actions button:hover': `
    background: #3a8eef;
  `,

  // ---------- Hover 模式 ----------
  'bt-hover-enabled': `
    border-bottom: 1px dashed #4a9eff;
    cursor: help;
  `,

  // ---------- 视频字幕 ----------
  'bt-subtitle-overlay': `
    position: absolute;
    bottom: 60px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 2147483647;
    text-align: center;
    pointer-events: none;
    max-width: 80%;
    transition: opacity 0.2s ease;
  `,

  'bt-subtitle-original': `
    display: block;
    padding: 4px 16px;
    margin-bottom: 4px;
    font-size: 20px;
    font-weight: 600;
    color: #fff;
    text-shadow: 0 0 4px rgba(0,0,0,0.9), 0 0 8px rgba(0,0,0,0.7), 1px 1px 2px rgba(0,0,0,0.8);
    line-height: 1.4;
    font-family: 'YouTube Noto', Roboto, 'Arial Unicode Ms', sans-serif;
  `,

  'bt-subtitle-translated': `
    display: block;
    padding: 3px 16px;
    font-size: 17px;
    color: #ffe066;
    text-shadow: 0 0 4px rgba(0,0,0,0.9), 0 0 8px rgba(0,0,0,0.7), 1px 1px 2px rgba(0,0,0,0.8);
    line-height: 1.4;
    font-family: 'YouTube Noto', Roboto, 'Arial Unicode Ms', sans-serif;
    font-weight: 500;
  `,

  'bt-subtitle-btn': `
    position: absolute;
    top: 10px;
    right: 10px;
    z-index: 2147483647;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.6);
    color: #fff;
    border: 2px solid rgba(255, 255, 255, 0.3);
    font-size: 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    pointer-events: auto;
  `,

  'bt-subtitle-btn:hover': `
    background: rgba(74, 158, 255, 0.8);
    border-color: #4a9eff;
  `,
};

/** 动画帧（不能用选择器格式，单独定义） */
const KEYFRAMES: Record<string, string> = {
  'bt-fadeIn': `
    from { opacity: 0; transform: translateY(-2px); }
    to   { opacity: 1; transform: translateY(0); }
  `,
  'bt-spin': `
    to { transform: rotate(360deg); }
  `,
  'bt-bubbleIn': `
    from { opacity: 0; transform: translateY(-4px); }
    to   { opacity: 1; transform: translateY(0); }
  `,
  'bt-slideIn': `
    from { opacity: 0; transform: translateX(20px); }
    to   { opacity: 1; transform: translateX(0); }
  `,
};

/** 构建完整 CSS 字符串 */
function buildCSS(): string {
  let css = '';

  // 选择器样式
  for (const [selector, body] of Object.entries(STYLES)) {
    css += `.${selector} { ${body} }\n`;
  }

  // 动画帧
  for (const [name, body] of Object.entries(KEYFRAMES)) {
    css += `@keyframes ${name} { ${body} }\n`;
  }

  return css;
}

/** 注入样式到页面 */
export function injectStyles(): void {
  if (document.getElementById(STYLE_ID)) return;

  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = buildCSS();
  document.head.appendChild(style);
}

/** 移除样式 */
export function removeStyles(): void {
  document.getElementById(STYLE_ID)?.remove();
}

/** 获取某个 class 的样式名（用于 createElement 后设置 className） */
export function cls(name: string): string {
  return name;
}
