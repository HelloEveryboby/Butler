/* ============================================================
   字幕翻译 — 实时翻译视频字幕（YouTube / B站 / 通用）
   拦截字幕 DOM → 翻译 → 双语覆盖显示
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { detectLanguageQuick } from '../../utils/languages';

// ---------- 站点字幕选择器 ----------
interface SubtitleSiteConfig {
  name: string;
  hostPatterns: RegExp[];
  /** 字幕文本元素选择器 */
  subtitleSelector: string;
  /** 字幕容器选择器（用于注入翻译字幕） */
  containerSelector: string;
  /** 是否是逐词字幕（YouTube 的 word-by-word 模式） */
  isWordByWord?: boolean;
  /** 提取文本的额外逻辑 */
  extractText?: (el: Element) => string;
}

const SUBTITLE_SITES: SubtitleSiteConfig[] = [
  {
    name: 'YouTube',
    hostPatterns: [/youtube\.com/, /youtu\.be/],
    subtitleSelector: '.ytp-caption-segment',
    containerSelector: '.ytp-caption-window-container',
    isWordByWord: true,
  },
  {
    name: 'Bilibili',
    hostPatterns: [/bilibili\.com/],
    subtitleSelector: '.bpx-player-subtitle-wrap .bpx-player-subtitle-line, .bilibili-player-video-subtitle .diy-tag-content, .bpx-player-dm-wrap + div span',
    containerSelector: '.bpx-player-subtitle-wrap, .bilibili-player-video-subtitle',
  },
  {
    name: 'Netflix',
    hostPatterns: [/netflix\.com/],
    subtitleSelector: '.player-timedtext-text-container span',
    containerSelector: '.player-timedtext-text-container',
  },
  {
    name: '通用 HTML5 Video',
    hostPatterns: [/.*/], // 兜底
    subtitleSelector: 'video::cue, track[kind="subtitles"]',
    containerSelector: 'video',
  },
];

// ---------- 状态 ----------
let currentSite: SubtitleSiteConfig | null = null;
let subtitleObserver: MutationObserver | null = null;
let translatedOverlay: HTMLDivElement | null = null;
let isEnabled = false;
let config: TranslateConfig | null = null;
let lastTranslatedText = '';
let translateDebounce: ReturnType<typeof setTimeout> | null = null;

// 翻译缓存（字幕级，防止重复翻译同一句）
const subtitleCache = new Map<string, string>();

/** 初始化字幕翻译 */
export function initSubtitleTranslate(cfg: TranslateConfig): void {
  config = cfg;
  currentSite = detectSite();
  if (!currentSite) {
    console.log('[ButlerTranslate] No subtitle site matched for', location.hostname);
    return;
  }
  console.log(`[ButlerTranslate] Subtitle translation ready for ${currentSite.name}`);
}

/** 启动字幕翻译 */
export function startSubtitleTranslate(): void {
  if (!currentSite || !config) return;
  isEnabled = true;

  // 创建翻译字幕覆盖层
  createOverlay();

  // 监听字幕 DOM 变化
  startSubtitleObserver();

  console.log('[ButlerTranslate] Subtitle translation started');
}

/** 停止字幕翻译 */
export function stopSubtitleTranslate(): void {
  isEnabled = false;
  stopSubtitleObserver();
  removeOverlay();
  lastTranslatedText = '';
  console.log('[ButlerTranslate] Subtitle translation stopped');
}

/** 切换 */
export function toggleSubtitleTranslate(cfg: TranslateConfig): boolean {
  if (isEnabled) {
    stopSubtitleTranslate();
  } else {
    config = cfg;
    startSubtitleTranslate();
  }
  return isEnabled;
}

export function isSubtitleTranslateEnabled(): boolean {
  return isEnabled;
}

// ---------- 站点检测 ----------
function detectSite(): SubtitleSiteConfig | null {
  const hostname = location.hostname;
  for (const site of SUBTITLE_SITES) {
    if (site.hostPatterns.some(p => p.test(hostname))) {
      return site;
    }
  }
  return null;
}

// ---------- 字幕观察 ----------
function startSubtitleObserver(): void {
  stopSubtitleObserver();

  subtitleObserver = new MutationObserver(() => {
    if (!isEnabled) return;
    // 防抖：字幕可能快速连续变化
    if (translateDebounce) clearTimeout(translateDebounce);
    translateDebounce = setTimeout(() => {
      processSubtitles();
    }, 100);
  });

  // 观察整个 body 的子树变化
  subtitleObserver.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true,
  });
}

function stopSubtitleObserver(): void {
  subtitleObserver?.disconnect();
  subtitleObserver = null;
  if (translateDebounce) {
    clearTimeout(translateDebounce);
    translateDebounce = null;
  }
}

// ---------- 处理字幕 ----------
async function processSubtitles(): Promise<void> {
  if (!currentSite || !config || !isEnabled) return;

  // 提取当前显示的字幕文本
  const subtitleElements = document.querySelectorAll(currentSite.subtitleSelector);
  if (subtitleElements.length === 0) return;

  // 合并所有字幕段的文本
  const texts: string[] = [];
  for (const el of subtitleElements) {
    const text = currentSite.extractText
      ? currentSite.extractText(el)
      : el.textContent?.trim();
    if (text) texts.push(text);
  }

  const combinedText = texts.join(' ').trim();
  if (!combinedText || combinedText.length < 2) {
    hideOverlay();
    return;
  }

  // 跳过已翻译的同一句
  if (combinedText === lastTranslatedText) return;

  // 检查语言
  const detected = detectLanguageQuick(combinedText);
  if (detected === config.targetLang) {
    hideOverlay();
    return;
  }

  // 查缓存
  const cached = subtitleCache.get(combinedText);
  if (cached) {
    showTranslation(combinedText, cached);
    return;
  }

  // 翻译
  try {
    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts: [combinedText],
      to: config.targetLang,
    });

    if (resp.type === 'TRANSLATE_RESULT' && resp.results[0]) {
      const translated = resp.results[0].translated;
      // 写缓存
      if (subtitleCache.size > 500) {
        // 淘汰最旧的
        const firstKey = subtitleCache.keys().next().value;
        if (firstKey !== undefined) subtitleCache.delete(firstKey);
      }
      subtitleCache.set(combinedText, translated);

      showTranslation(combinedText, translated);
    }
  } catch (err) {
    console.warn('[ButlerTranslate] Subtitle translation failed:', err);
  }
}

// ---------- 翻译覆盖层 ----------
function createOverlay(): void {
  removeOverlay();

  translatedOverlay = document.createElement('div');
  translatedOverlay.className = 'bt-subtitle-overlay';
  translatedOverlay.innerHTML = `
    <div class="bt-subtitle-original"></div>
    <div class="bt-subtitle-translated"></div>
  `;

  // 定位到视频播放器底部
  const videoContainer = findVideoContainer();
  if (videoContainer) {
    videoContainer.style.position = videoContainer.style.position || 'relative';
    videoContainer.appendChild(translatedOverlay);
  } else {
    // 兜底：fixed 定位
    translatedOverlay.style.position = 'fixed';
    translatedOverlay.style.bottom = '80px';
    translatedOverlay.style.left = '50%';
    translatedOverlay.style.transform = 'translateX(-50%)';
    document.body.appendChild(translatedOverlay);
  }
}

function removeOverlay(): void {
  translatedOverlay?.remove();
  translatedOverlay = null;
}

function showTranslation(original: string, translated: string): void {
  if (!translatedOverlay) createOverlay();
  if (!translatedOverlay) return;

  lastTranslatedText = original;

  const origEl = translatedOverlay.querySelector('.bt-subtitle-original')!;
  const transEl = translatedOverlay.querySelector('.bt-subtitle-translated')!;

  origEl.textContent = original;
  transEl.textContent = translated;

  translatedOverlay.style.display = 'block';
  translatedOverlay.style.opacity = '1';
}

function hideOverlay(): void {
  if (translatedOverlay) {
    translatedOverlay.style.opacity = '0';
    setTimeout(() => {
      if (translatedOverlay) translatedOverlay.style.display = 'none';
    }, 200);
  }
}

// ---------- 查找视频容器 ----------
function findVideoContainer(): HTMLElement | null {
  // YouTube
  const yt = document.querySelector('.html5-video-player');
  if (yt) return yt as HTMLElement;

  // Bilibili
  const bili = document.querySelector('.bpx-player-video-wrap, .bilibili-player-video-wrap');
  if (bili) return bili as HTMLElement;

  // Netflix
  const netflix = document.querySelector('.VideoContainer');
  if (netflix) return netflix as HTMLElement;

  // 通用：找最近的 video 祖先
  const video = document.querySelector('video');
  if (video) {
    let parent = video.parentElement;
    let depth = 0;
    while (parent && depth < 5) {
      const style = window.getComputedStyle(parent);
      if (style.position === 'relative' || style.position === 'absolute') {
        return parent;
      }
      parent = parent.parentElement;
      depth++;
    }
    return video.parentElement;
  }

  return null;
}
