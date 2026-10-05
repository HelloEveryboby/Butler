/* ============================================================
   字幕翻译 — 实时翻译视频字幕（YouTube / B站 / 通用）
   拦截字幕 DOM → 翻译 → 双语覆盖显示
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { detectLanguageQuick } from '../../utils/languages';
import {
  detectMeetingSite,
  shouldStickToBottom,
  stickToBottom,
} from './meeting-translate';
import {
  saveSubtitleSession,
  estimateCueDuration,
  SubtitlePair,
} from '../../utils/subtitle-history';

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
  /**
   * 走 video.textTracks 通道（而非 DOM 选择器）。
   * 适用于所有没有稳定字幕 DOM 的播放器，例如原生 <video><track>。
   */
  useTextTrack?: boolean;
  /** 会议平台：字幕/转写面板（role 列表）与滚动容器 */
  isMeeting?: true;
  panelSelector?: string;
  entrySelector?: string;
  scrollSelector?: string;
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
    // 注意：不要用 'video::cue' 当选择器 —— ::cue 是 CSS 伪元素，
    // querySelectorAll 永远匹配不到节点，必须走 textTracks 通道。
    useTextTrack: true,
    subtitleSelector: '',
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

  // 两条通道：DOM 字幕节点 或 video.textTracks
  if (currentSite.useTextTrack) {
    startTextTrackWatch();
  } else {
    startSubtitleObserver();
  }

  console.log('[ButlerTranslate] Subtitle translation started');
}

/** 停止字幕翻译 */
export function stopSubtitleTranslate(): void {
  isEnabled = false;
  stopSubtitleObserver();
  stopTextTrackWatch();
  removeOverlay();
  lastTranslatedText = '';
  void flushLivePairs(); // 保存实时字幕历史（双语导出用）
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
  // 会议平台优先（Zoom / Meet / Teams 的字幕 DOM 是 role 列表 + 滚动容器）
  const meeting = detectMeetingSite(hostname);
  if (meeting) return meeting;
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

// ---------- TextTrack 通道（原生 <video><track> 的字幕） ----------
let textTrackHandler: (() => void) | null = null;
let watchedVideos: HTMLVideoElement[] = [];

function startTextTrackWatch(): void {
  stopTextTrackWatch();

  const collect = () => Array.from(document.querySelectorAll('video')) as HTMLVideoElement[];
  watchedVideos = collect();

  textTrackHandler = () => {
    if (!isEnabled || !config) return;
    // 防抖，与 DOM 通道共用同一套节奏
    if (translateDebounce) clearTimeout(translateDebounce);
    translateDebounce = setTimeout(() => {
      const text = readActiveCues();
      if (text) void translateAndShow(text);
      else hideOverlay();
    }, 150);
  };

  for (const video of watchedVideos) {
    video.addEventListener('timeupdate', textTrackHandler);
    video.addEventListener('seeked', textTrackHandler);
    // 字幕轨可能在播放后才加载，监听 track 列表变化
    video.textTracks?.addEventListener?.('addtrack', textTrackHandler);
  }

  // 页面上 video 可能晚于扩展出现（SPA），轮询补齐
  const poll = window.setInterval(() => {
    const now = collect();
    for (const v of now) {
      if (!watchedVideos.includes(v)) {
        v.addEventListener('timeupdate', textTrackHandler!);
        v.addEventListener('seeked', textTrackHandler!);
        v.textTracks?.addEventListener?.('addtrack', textTrackHandler!);
        watchedVideos.push(v);
      }
    }
    if (!isEnabled) window.clearInterval(poll);
  }, 2000);
}

function stopTextTrackWatch(): void {
  if (textTrackHandler) {
    for (const v of watchedVideos) {
      v.removeEventListener('timeupdate', textTrackHandler);
      v.removeEventListener('seeked', textTrackHandler);
      v.textTracks?.removeEventListener?.('addtrack', textTrackHandler);
    }
  }
  watchedVideos = [];
  textTrackHandler = null;
}

/** 读取当前时刻正在显示的所有 cue 文本 */
function readActiveCues(): string | null {
  const parts: string[] = [];
  for (const video of watchedVideos) {
    if (!video.textTracks) continue;
    for (const track of Array.from(video.textTracks)) {
      if (track.mode !== 'showing' || !track.cues) continue;
      for (const cue of Array.from(track.cues)) {
        const c = cue as any;
        if (typeof c.startTime === 'number' && typeof c.endTime === 'number'
            && c.startTime <= video.currentTime && c.endTime >= video.currentTime) {
          const t = String(c.text || '').replace(/<[^>]+>/g, '').trim();
          if (t) parts.push(t);
        }
      }
    }
  }
  const text = parts.join(' ').trim();
  return text.length >= 2 ? text : null;
}

// ---------- 处理字幕 ----------
async function processSubtitles(): Promise<void> {
  if (!currentSite || !config || !isEnabled) return;

  // 会议平台：优先处理转写面板（逐条插入译文 + 滚动跟随）
  if (currentSite.isMeeting && currentSite.panelSelector) {
    await processMeetingPanel();
  }

  // 提取当前显示的字幕文本（实时 caption → 覆盖层）
  if (!currentSite.subtitleSelector) return;
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

  await translateAndShow(combinedText);
}

/**
 * 会议字幕面板：逐条插入译文（不覆盖原字幕），并处理滚动跟随。
 * 字幕 DOM 是带 role 的 div 列表，条目会持续追加，
 * 每个条目只翻译一次（data-bt-done 标记）。
 */
async function processMeetingPanel(): Promise<void> {
  if (!currentSite || !config) return;
  const panel = document.querySelector(currentSite.panelSelector!);
  if (!panel) return;

  const entrySelector = currentSite.entrySelector || '[role="listitem"]';
  const entries = Array.from(panel.querySelectorAll(entrySelector))
    .filter(el => !el.hasAttribute('data-bt-done'))
    .filter(el => (el.textContent || '').trim().length >= 2);
  if (entries.length === 0) return;

  const texts = entries.map(el => (el.textContent || '').trim());

  try {
    const resp = await sendMessage({
      type: 'TRANSLATE',
      texts,
      to: config.targetLang,
    });
    if (resp.type !== 'TRANSLATE_RESULT') return;

    // 滚动跟随：用户贴底才保持贴底，往上翻阅历史时不打扰
    const scrollEl = currentSite.scrollSelector
      ? panel.closest(currentSite.scrollSelector) || document.querySelector(currentSite.scrollSelector)
      : (panel as HTMLElement);
    const stick = shouldStickToBottom(scrollEl as Element | null);

    entries.forEach((el, i) => {
      const translated = resp.results[i]?.translated;
      el.setAttribute('data-bt-done', '1');
      if (translated && translated !== texts[i]) {
        const div = document.createElement('div');
        div.className = 'bt-meeting-translation';
        div.textContent = translated;
        el.appendChild(div);
      }
    });

    if (stick) stickToBottom(scrollEl as Element | null);
  } catch (err) {
    console.warn('[ButlerTranslate] Meeting panel translation failed:', err);
  }
}

/** 翻译并显示（DOM 通道与 TextTrack 通道共用） */
async function translateAndShow(combinedText: string): Promise<void> {
  if (!config || !isEnabled) return;

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

      recordLivePair(combinedText, translated);
      showTranslation(combinedText, translated);
    }
  } catch (err) {
    console.warn('[ButlerTranslate] Subtitle translation failed:', err);
  }
}

// ---------- 实时字幕翻译历史（供双语 SRT/VTT 导出，时间轴为近似值） ----------
const livePairs: SubtitlePair[] = [];
let liveClockMs = 0;
let liveSaveTimer: ReturnType<typeof setTimeout> | null = null;

function recordLivePair(original: string, translated: string): void {
  const duration = estimateCueDuration(original);
  livePairs.push({
    startMs: liveClockMs,
    endMs: liveClockMs + duration,
    original,
    translated,
  });
  liveClockMs += duration;
  // 节流持久化
  if (!liveSaveTimer) {
    liveSaveTimer = setTimeout(() => {
      liveSaveTimer = null;
      void flushLivePairs();
    }, 5000);
  }
}

async function flushLivePairs(): Promise<void> {
  if (livePairs.length === 0) return;
  await saveSubtitleSession({
    id: `live-${location.hostname}`,
    ts: Date.now(),
    title: `字幕翻译-${location.hostname}`,
    targetLang: config?.targetLang || 'zh-CN',
    preciseTiming: false, // 实时字幕：时间轴为近似值
    pairs: [...livePairs],
  });
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
