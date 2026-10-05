/* ============================================================
   Butler Translate — Background Service Worker
   消息路由、翻译 API 代理、缓存、降级链、右键菜单
   ============================================================ */

import { loadConfig, saveConfig } from '../utils/storage';
import { TranslateConfig, MsgType, MsgResponse, TranslationResult, ProviderConfig, HistoryEntry, TranslateOptions, PageContext } from '../utils/types';
import { TranslationCache } from './cache';
import { createProvider, createProviderWithFallback } from './providers/registry';
import { TranslationProvider } from '../utils/types';
import { withTimeout, retryWithSplit } from '../utils/retry';
import { applyGlossary } from './glossary';
import { ButlerBhlClient } from './bhl';
import { getPageContext, LlmCaller } from './ctx';
import { resolvePresetForSite } from '../utils/presets';

// ---------- 全局状态 ----------
let config: TranslateConfig | null = null;
const cache = new TranslationCache();
const HISTORY_KEY = 'butler_translate_history';

// ---------- 历史 ----------
async function loadHistory(): Promise<HistoryEntry[]> {
  try {
    const r = await chrome.storage.local.get(HISTORY_KEY);
    return (r[HISTORY_KEY] as HistoryEntry[]) || [];
  } catch {
    return [];
  }
}

async function saveHistory(entries: HistoryEntry[]): Promise<void> {
  try {
    const max = config?.historyMaxSize ?? 500;
    const trimmed = entries.slice(-max);
    await chrome.storage.local.set({ [HISTORY_KEY]: trimmed });
  } catch (e) {
    console.warn('[ButlerTranslate] History save failed:', e);
  }
}

async function recordHistory(results: TranslationResult[], to: string): Promise<void> {
  if (!config?.historyEnabled) return;
  const entries = await loadHistory();
  const ts = Date.now();
  for (const r of results) {
    entries.push({
      original: r.original,
      translated: r.translated,
      to,
      provider: r.provider,
      ts,
    });
  }
  await saveHistory(entries);
}

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

// ---------- AI 上下文 / LLM 调用者 ----------
/** 找一个可用的 LLM 调用者（活跃 Provider 优先，其次任一已启用的 OpenAI 兼容 Provider） */
function findLlmCaller(): LlmCaller | null {
  const cfg = config;
  if (!cfg) return null;
  const active = cfg.providers.find(p => p.id === cfg.activeProviderId);
  const candidates = [active, ...cfg.providers.filter(p => p.enabled && p.id !== active?.id)];
  for (const p of candidates) {
    if (!p || !p.enabled) continue;
    if (p.type === 'openai-compat' || p.type === 'deepseek') {
      return createProvider(p) as unknown as LlmCaller;
    }
  }
  return null;
}

/** 从 URL 取 hostname（预设站点绑定用） */
function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

/** 翻译链是否包含 LLM 型 Provider（非 LLM 无需生成上下文，省一次调用） */
function chainUsesLlm(providerId?: string): boolean {
  const isLlm = (t?: string) => t === 'openai-compat' || t === 'deepseek';
  const cfg = config!;
  if (providerId) {
    return isLlm(cfg.providers.find(p => p.id === providerId)?.type);
  }
  return cfg.fallbackChain.some(id => {
    const p = cfg.providers.find(pp => pp.id === id);
    return !!p && p.enabled && isLlm(p.type);
  });
}

// ---------- 翻译处理 ----------
async function handleTranslate(
  texts: string[],
  to: string,
  providerId?: string,
  context?: { url: string; text: string }
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

    // 术语表 + 页面上下文 + 行业预设（进 prompt；事后 applyGlossary 兜底）
    const glossary = config!.glossary || [];
    const preset = resolvePresetForSite(
      hostnameOf(context?.url || ''),
      config!.presets || [],
      config!.sitePresetBindings || [],
      config!.activePresetId
    );
    let pageContext: PageContext | null = null;
    if (config!.ctxEnabled && context?.text && chainUsesLlm(providerId)) {
      pageContext = await getPageContext(context.url, context.text, findLlmCaller());
    }
    const opts: TranslateOptions = { glossary, context: pageContext ?? undefined, preset };

    // 翻译未命中的（原文直译，术语约束在 prompt 里）
    const missTexts = Array.from(misses.values());
    const translated = await withTimeout(
      retryWithSplit(missTexts, async (batch) => {
        if (provider.translateBatch) {
          return await provider.translateBatch(batch, 'auto', to, opts);
        }
        return Promise.all(batch.map(t => provider.translate(t, 'auto', to, opts)));
      }),
      60000,
      'Translation'
    );

    // 事后校验：译文兜底套术语表（进 prompt + 事后替换双保险）
    const finalTranslated = translated.map(t => applyGlossary(t, glossary));

    // 写入缓存
    const missKeys = Array.from(misses.keys());
    const originalMissTexts = Array.from(misses.values());
    finalTranslated.forEach((t, i) => {
      cache.set(originalMissTexts[i], to, t, provider.name);
    });

    // 合并结果
    const results: TranslationResult[] = texts.map((text, idx) => {
      if (hits.has(idx)) {
        return { original: text, translated: hits.get(idx)!, provider: 'cache' };
      }
      const missIdx = missKeys.indexOf(idx);
      return {
        original: text,
        translated: missIdx >= 0 ? finalTranslated[missIdx] : text,
        provider: provider.name,
      };
    });

    // 记录历史（忽略缓存命中的，避免重复）
    const newResults = results.filter(r => r.provider !== 'cache');
    if (newResults.length) recordHistory(newResults, to);

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

// ---------- 截图翻译（转发到 Butler 后端 BHL） ----------
let bhlClient: ButlerBhlClient | null = null;

function getBhlClient(): ButlerBhlClient {
  const url = config?.butlerBackendUrl || 'ws://127.0.0.1:8765';
  if (!bhlClient) bhlClient = new ButlerBhlClient(url);
  return bhlClient;
}

async function handleImageTranslate(base64: string): Promise<MsgResponse> {
  try {
    const client = getBhlClient();
    const result = await client.translateImage(base64, 'auto', config?.targetLang || 'zh-CN');
    return {
      type: 'IMAGE_TRANSLATE_RESULT',
      original: result.text,
      translated: result.translated,
    };
  } catch (err) {
    return {
      type: 'TRANSLATE_ERROR',
      error: `图片翻译需要 Butler 后端（${config?.butlerBackendUrl || 'ws://127.0.0.1:8765'}）：${err}`,
    };
  }
}

// ---------- 可见区域截图（content script 无权调 captureVisibleTab，由这里中转） ----------
async function handleCaptureVisibleTab(): Promise<MsgResponse> {
  try {
    const dataUrl = await chrome.tabs.captureVisibleTab({ format: 'png' });
    return { type: 'CAPTURE_RESULT', dataUrl };
  } catch (err) {
    return { type: 'TRANSLATE_ERROR', error: `截图失败: ${err}` };
  }
}

// ---------- 双语 PDF 导出（转发给 Butler 后端 CLI，不支持时如实报错） ----------
async function handleExportPdf(pdfBase64: string, filename: string, to: string): Promise<MsgResponse> {
  const backendUrl = config?.butlerBackendUrl || 'ws://127.0.0.1:8765';
  const client = getBhlClient();
  const available = await client.isAvailable();
  if (!available) {
    return {
      type: 'EXPORT_RESULT',
      success: false,
      message: `Butler 后端未连接（${backendUrl}）：请启动 Butler 后端或使用文档翻译导出 TXT/EPUB`,
    };
  }
  try {
    const result = await client.exportPdf(pdfBase64, filename, to);
    return {
      type: 'EXPORT_RESULT',
      success: true,
      message: '双语 PDF 导出完成',
      dataUrl: result.dataUrl,
      filename: result.filename,
    };
  } catch (err) {
    return {
      type: 'EXPORT_RESULT',
      success: false,
      message: `双语 PDF 导出失败：${err}。请启动支持 export.pdf 的 Butler 后端，或使用文档翻译导出 TXT/EPUB`,
    };
  }
}

// ---------- 术语表与 Butler 后端双向同步（发送侧） ----------
async function handleGlossaryPush(): Promise<MsgResponse> {
  const backendUrl = config?.butlerBackendUrl || 'ws://127.0.0.1:8765';
  const client = getBhlClient();
  if (!(await client.isAvailable())) {
    return {
      type: 'ACTION_RESULT',
      success: false,
      message: `Butler 后端未连接（${backendUrl}）：无法推送术语表`,
    };
  }
  try {
    const list = config!.glossary || [];
    let pushed = 0;
    for (const g of list) {
      await client.glossaryAdd(g.source, g.target);
      pushed++;
    }
    return { type: 'ACTION_RESULT', success: true, message: `已推送 ${pushed} 条术语到 Butler 后端` };
  } catch (err) {
    return { type: 'ACTION_RESULT', success: false, message: `术语推送失败：${err}` };
  }
}

async function handleGlossaryPull(): Promise<MsgResponse> {
  const backendUrl = config?.butlerBackendUrl || 'ws://127.0.0.1:8765';
  const client = getBhlClient();
  if (!(await client.isAvailable())) {
    return {
      type: 'ACTION_RESULT',
      success: false,
      message: `Butler 后端未连接（${backendUrl}）：无法拉取术语表`,
    };
  }
  try {
    const remote = await client.glossaryList();
    const list = config!.glossary ? [...config!.glossary] : [];
    let added = 0;
    for (const t of remote) {
      const idx = list.findIndex(g => g.source.toLowerCase() === t.source.toLowerCase());
      if (idx >= 0) {
        list[idx] = { source: t.source, target: t.target };
      } else {
        list.push({ source: t.source, target: t.target });
        added++;
      }
    }
    await saveConfig({ glossary: list });
    config = await loadConfig();
    return {
      type: 'ACTION_RESULT',
      success: true,
      message: `已从 Butler 后端拉取 ${remote.length} 条术语（新增 ${added} 条）`,
    };
  } catch (err) {
    return { type: 'ACTION_RESULT', success: false, message: `术语拉取失败：${err}` };
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
        response = await handleTranslate(msg.texts, msg.to, msg.providerId, msg.context);
        break;
      case 'TRANSLATE_SELECTION':
        response = await handleTranslate([msg.text], config.targetLang);
        break;
      case 'TRANSLATE_IMAGE':
        response = await handleImageTranslate(msg.base64);
        break;
      case 'CAPTURE_VISIBLE_TAB':
        response = await handleCaptureVisibleTab();
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
      case 'GET_GLOSSARY':
        response = { type: 'GLOSSARY', entries: config!.glossary || [] };
        break;
      case 'ADD_GLOSSARY': {
        const list = config!.glossary || [];
        const idx = list.findIndex(g => g.source === msg.source);
        if (idx >= 0) list[idx] = { source: msg.source, target: msg.target };
        else list.push({ source: msg.source, target: msg.target });
        await saveConfig({ glossary: list });
        config = await loadConfig();
        // 尽力同步到 Butler 后端（后端未启动时静默失败，不影响本地保存）
        getBhlClient().isAvailable().then(ok => {
          if (ok) getBhlClient().glossaryAdd(msg.source, msg.target).catch(() => {});
        }).catch(() => {});
        response = { type: 'OK' };
        break;
      }
      case 'REMOVE_GLOSSARY': {
        const list = (config!.glossary || []).filter(g => g.source !== msg.source);
        await saveConfig({ glossary: list });
        config = await loadConfig();
        response = { type: 'OK' };
        break;
      }
      case 'GET_HISTORY': {
        const entries = await loadHistory();
        response = { type: 'HISTORY', entries: entries.slice(-(msg.limit ?? 50)).reverse() };
        break;
      }
      case 'CLEAR_HISTORY':
        await chrome.storage.local.remove(HISTORY_KEY);
        response = { type: 'OK' };
        break;
      case 'GET_PAGE_CONTEXT': {
        const ctx = await getPageContext(msg.url, msg.text, findLlmCaller());
        response = { type: 'PAGE_CONTEXT', context: ctx };
        break;
      }
      case 'EXPORT_PDF':
        response = await handleExportPdf(msg.pdfBase64, msg.filename, msg.to);
        break;
      case 'SYNC_GLOSSARY_PUSH':
        response = await handleGlossaryPush();
        break;
      case 'SYNC_GLOSSARY_PULL':
        response = await handleGlossaryPull();
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
