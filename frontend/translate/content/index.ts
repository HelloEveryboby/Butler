/* ============================================================
   Butler Translate — Content Script 入口
   初始化所有子模块，监听 Background 消息
   ============================================================ */

import { loadConfig } from '../utils/storage';
import { TranslateConfig } from '../utils/types';
import { sendMessage } from '../utils/messaging';
import { injectStyles } from './styles/styles';

// Features
import { startFullTranslate, stopTranslate, toggleTranslate, isTranslated } from './features/full-translate';
import { initSelectionTranslate } from './features/selection-translate';
import { initInputTranslate } from './features/input-translate';
import { initClipboardTranslate } from './features/clipboard-translate';
import { initScreenshotTranslate } from './features/screenshot-translate';
import { initSubtitleTranslate, toggleSubtitleTranslate, isSubtitleTranslateEnabled, stopSubtitleTranslate } from './features/subtitle-translate';
import { initPDFTranslate, startPDFTranslate, stopPDFTranslate, isPDFPage } from './features/pdf-translate';
import { showDocumentTranslator, removeDocumentTranslator } from './features/document-translate';
import { translateImage, translateDocumentImages } from './features/image-translate';

// UI
import { initFloatingBall, updateBallState } from './ui/floating-ball';

// Observers
import { startObserving, stopObserving } from './observers/mutation';
import { initRouterObserver } from './observers/router';

// 状态
let config: TranslateConfig | null = null;
let initialized = false;

async function init() {
  if (initialized) return;
  initialized = true;

  config = await loadConfig();

  // 注入样式（纯 TS 生成，无 CSS 文件）
  injectStyles();

  // 检查是否在排除列表
  if (isExcludedSite()) {
    console.log('[ButlerTranslate] Site excluded:', location.hostname);
    return;
  }

  console.log('[ButlerTranslate] Content script initialized on', location.hostname);

  // 初始化各模块
  initSelectionTranslate(config);
  initInputTranslate(config);
  initClipboardTranslate(config);
  initScreenshotTranslate(config);
  initSubtitleTranslate(config);
  initPDFTranslate(config);

  initFloatingBall(config, () => {
    if (config) toggleTranslate(config);
    updateBallState(isTranslated());
  });

  // SPA 路由监听
  initRouterObserver(() => {
    if (isTranslated() && config) {
      stopTranslate();
      startFullTranslate(config);
    }
  });

  // 自动翻译
  if (config.autoTranslate) {
    startFullTranslate(config);
    updateBallState(true);
  }

  // 监听来自 Background 的消息
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'TOGGLE_TRANSLATE') {
      if (config) toggleTranslate(config);
      updateBallState(isTranslated());
      sendResponse({ type: 'OK' });
    }
    if (msg.type === 'TOGGLE_SUBTITLE') {
      if (config) {
        const enabled = toggleSubtitleTranslate(config);
        sendResponse({ type: 'OK', enabled });
      }
    }
    if (msg.type === 'TOGGLE_PDF') {
      if (config && isPDFPage()) {
        await startPDFTranslate(config);
        sendResponse({ type: 'OK', enabled: true });
      } else {
        sendResponse({ type: 'OK', enabled: false, message: '当前页面不是 PDF' });
      }
    }
    if (msg.type === 'SHOW_DOC_TRANSLATOR') {
      if (config) showDocumentTranslator(config);
      sendResponse({ type: 'OK' });
    }
    if (msg.type === 'TRANSLATE_IMAGE_CONTEXT' && msg.imageUrl && config) {
      const img = document.querySelector(`img[src="${msg.imageUrl}"]`) as HTMLImageElement;
      if (img) {
        try {
          const result = await translateImage(img, config, 'side');
          img.parentNode?.insertBefore(result, img);
          img.style.display = 'none';
        } catch (err) {
          console.error('[ButlerTranslate] Image context translate failed:', err);
        }
      }
      sendResponse({ type: 'OK' });
    }
    if (msg.type === 'TRANSLATE_SELECTION' && msg.text) {
      // 从右键菜单触发的划词翻译
      showQuickTranslation(msg.text, config!);
      sendResponse({ type: 'OK' });
    }
    return true;
  });
}

function isExcludedSite(): boolean {
  if (!config) return false;
  const hostname = location.hostname;
  return config.excludeSites.some(site => hostname.includes(site));
}

/** 快速翻译（右键菜单触发） */
async function showQuickTranslation(text: string, cfg: TranslateConfig): Promise<void> {
  try {
    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts: [text],
      to: cfg.targetLang,
    });

    if (resp.type === 'TRANSLATE_RESULT') {
      const translated = resp.results[0]?.translated;
      if (translated) {
        // 创建一个临时气泡显示
        const bubble = document.createElement('div');
        bubble.className = 'bt-bubble';
        bubble.style.position = 'fixed';
        bubble.style.top = '50%';
        bubble.style.left = '50%';
        bubble.style.transform = 'translate(-50%, -50%)';
        bubble.style.zIndex = '2147483647';
        bubble.innerHTML = `
          <div class="bt-bubble-content">${translated}</div>
          <div class="bt-bubble-actions">
            <button class="bt-bubble-copy">📋</button>
            <button class="bt-bubble-close">✕</button>
          </div>
        `;
        document.body.appendChild(bubble);

        bubble.querySelector('.bt-bubble-close')?.addEventListener('click', () => bubble.remove());
        bubble.querySelector('.bt-bubble-copy')?.addEventListener('click', () => {
          navigator.clipboard.writeText(translated);
          bubble.remove();
        });

        setTimeout(() => bubble.remove(), 8000);
      }
    }
  } catch (err) {
    console.error('[ButlerTranslate] Quick translation failed:', err);
  }
}

// 启动
init();
