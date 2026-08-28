/* ============================================================
   Butler Translate — Background Service Worker
   消息路由、翻译 API 代理、缓存、降级链、右键菜单
   ============================================================ */

import { loadConfig, saveConfig } from '../utils/storage';
import { TranslateConfig, MsgType, MsgResponse, TranslationResult, ProviderConfig } from '../utils/types';
import { TranslationCache } from './cache';
import { createProvider, createProviderWithFallback } from './providers/registry';
import { TranslationProvider } from '../utils/types';
import { withTimeout, retryWithSplit } from '../utils/retry';

// ---------- 全局状态 ----------
let config: TranslateConfig | null = null;
const cache = new TranslationCache();

// ---------- 初始化 ----------
async function init() {
  config = await loadConfig();
  setupContextMenu();
  console.log('[ButlerTranslate] Service worker initialized');
}

// ---------- 获取活跃 Provider ----------
function getActiveProvider(): TranslationProvider {
  if (!config) throw new Error('Config not loaded');
  const activeConfig = config.providers.find(p => p.id === config!.activeProviderId);
  if (!activeConfig) throw new Error(`Active provider not found: ${config.activeProviderId}`);
  return createProvider(activeConfig);
}

function getFallbackProvider(): TranslationProvider {
  if (!config) throw new Error('Config not loaded');
  const chain = config.fallbackChain
    .map(id => config!.providers.find(p => p.id === id))
    .filter((p): p is ProviderConfig => !!p && p.enabled);

  if (chain.length === 0) throw new Error('No enabled providers in fallback chain');

  const providers = chain.map(c => createProvider(c));
  return createProviderWithFallback(providers);
}

// ---------- 翻译处理 ----------
async function handleTranslate(
  texts: string[],
  to: string,
  providerId?: string
): Promise<MsgResponse> {
  try {
    const provider = providerId
      ? createProvider(config!.providers.find(p => p.id === providerId)!)
      : getFallbackProvider();

    // 查缓存
    const { hits, misses } = cache.batchLookup(texts, to);

    if (misses.size === 0) {
      // 全部命中缓存
      const results: TranslationResult[] = texts.map((text, idx) => ({
        original: text,
        translated: hits.get(idx)!,
        provider: 'cache',
      }));
      return { type: 'TRANSLATE_RESULT', results };
    }

    // 翻译未命中的
    const missTexts = Array.from(misses.values());
    const translated = await withTimeout(
      retryWithSplit(missTexts, async (batch) => {
        if (provider.translateBatch) {
          return await provider.translateBatch(batch, 'auto', to);
        }
        return Promise.all(batch.map(t => provider.translate(t, 'auto', to)));
      }),
      60000,
      'Translation'
    );

    // 写入缓存
    const missKeys = Array.from(misses.keys());
    translated.forEach((t, i) => {
      cache.set(missTexts[i], to, t, provider.name);
    });

    // 合并结果
    const results: TranslationResult[] = texts.map((text, idx) => {
      if (hits.has(idx)) {
        return { original: text, translated: hits.get(idx)!, provider: 'cache' };
      }
      const missIdx = missKeys.indexOf(idx);
      return {
        original: text,
        translated: missIdx >= 0 ? translated[missIdx] : text,
        provider: provider.name,
      };
    });

    return { type: 'TRANSLATE_RESULT', results };
  } catch (err) {
    return { type: 'TRANSLATE_ERROR', error: String(err) };
  }
}

// ---------- Provider 测试 ----------
async function handleTestProvider(providerConfig: ProviderConfig): Promise<MsgResponse> {
  try {
    const provider = createProvider(providerConfig);
    const result = await withTimeout(
      provider.translate('Hello, world!', 'en', 'zh-CN'),
      15000,
      'Provider test'
    );
    return {
      type: 'TEST_RESULT',
      success: true,
      message: `翻译成功: "Hello, world!" → "${result}"`,
    };
  } catch (err) {
    return {
      type: 'TEST_RESULT',
      success: false,
      message: `测试失败: ${err}`,
    };
  }
}

// ---------- 截图翻译（转发到 Butler 后端） ----------
async function handleImageTranslate(base64: string): Promise<MsgResponse> {
  // 通过 Butler BHL WebSocket 发送图片翻译请求
  // 这里简化为直接返回错误，实际需要连接 Butler 后端
  try {
    const butlerUrl = config?.butlerBackendUrl || 'ws://127.0.0.1:8765';
    // TODO: 实现 Butler WebSocket 图片翻译
    return {
      type: 'IMAGE_TRANSLATE_RESULT',
      original: '[截图翻译需要连接 Butler 后端]',
      translated: '请确保 Butler 后端正在运行',
    };
  } catch (err) {
    return { type: 'TRANSLATE_ERROR', error: String(err) };
  }
}

// ---------- 右键菜单 ----------
function setupContextMenu() {
  chrome.contextMenus?.removeAll?.(() => {
    chrome.contextMenus?.create?.({
      id: 'butler-translate-page',
      title: '翻译此页面',
      contexts: ['page'],
    });
    chrome.contextMenus?.create?.({
      id: 'butler-translate-selection',
      title: '翻译选中文本',
      contexts: ['selection'],
    });
    chrome.contextMenus?.create?.({
      id: 'butler-translate-image',
      title: '翻译此图片 (OCR)',
      contexts: ['image'],
    });
  });

  chrome.contextMenus?.onClicked?.addListener?.((info, tab) => {
    if (info.menuItemId === 'butler-translate-page' && tab?.id) {
      chrome.tabs.sendMessage(tab.id, { type: 'TOGGLE_TRANSLATE' });
    }
    if (info.menuItemId === 'butler-translate-selection' && info.selectionText && tab?.id) {
      chrome.tabs.sendMessage(tab.id, {
        type: 'TRANSLATE_SELECTION',
        text: info.selectionText,
      });
    }
    if (info.menuItemId === 'butler-translate-image' && info.srcUrl && tab?.id) {
      chrome.tabs.sendMessage(tab.id, {
        type: 'TRANSLATE_IMAGE_CONTEXT',
        imageUrl: info.srcUrl,
      });
    }
  });
}

// ---------- 消息路由 ----------
chrome.runtime.onMessage.addListener((msg: MsgType, sender, sendResponse) => {
  (async () => {
    if (!config) config = await loadConfig();

    let response: MsgResponse;

    switch (msg.type) {
      case 'TRANSLATE':
        response = await handleTranslate(msg.texts, msg.to, msg.providerId);
        break;
      case 'TRANSLATE_SELECTION':
        response = await handleTranslate([msg.text], config.targetLang);
        break;
      case 'TRANSLATE_IMAGE':
        response = await handleImageTranslate(msg.base64);
        break;
      case 'GET_CONFIG':
        response = { type: 'CONFIG', config };
        break;
      case 'SET_CONFIG':
        await saveConfig(msg.config);
        config = await loadConfig();
        response = { type: 'CONFIG', config };
        break;
      case 'GET_PROVIDERS':
        response = { type: 'PROVIDERS', providers: config.providers };
        break;
      case 'ADD_PROVIDER': {
        config.providers.push(msg.provider);
        await saveConfig({ providers: config.providers });
        response = { type: 'OK' };
        break;
      }
      case 'UPDATE_PROVIDER': {
        const idx = config.providers.findIndex(p => p.id === msg.id);
        if (idx >= 0) config.providers[idx] = { ...config.providers[idx], ...msg.patch };
        await saveConfig({ providers: config.providers });
        response = { type: 'OK' };
        break;
      }
      case 'DELETE_PROVIDER': {
        config.providers = config.providers.filter(p => p.id !== msg.id);
        await saveConfig({ providers: config.providers });
        response = { type: 'OK' };
        break;
      }
      case 'TEST_PROVIDER':
        response = await handleTestProvider(msg.provider);
        break;
      default:
        response = { type: 'TRANSLATE_ERROR', error: 'Unknown message type' };
    }

    sendResponse(response);
  })();
  return true; // 异步
});

// 快捷键监听
chrome.commands?.onCommand?.addListener?.((command) => {
  if (command === 'toggle-translate') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'TOGGLE_TRANSLATE' });
      }
    });
  }
});

init();
