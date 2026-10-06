/* ============================================================
   在线会议字幕 — Zoom / Google Meet / Teams
   ------------------------------------------------------------
   会议字幕 DOM 与普通视频不同：通常是带 role 的 div 列表，
   而且字幕/转写面板是滚动容器，需要处理滚动跟随。
   这里定义各平台的选择器（含多个 fallback）与滚动容器锚定配置。
   ⚠️ 会议平台前端更新频繁，selector 需要在真实 Zoom/Meet/Teams 中验证，
   匹配不到时自动退化为「video.textTracks」通道或整页字幕扫描，不静默失败。
   ============================================================ */

/** 会议平台字幕配置 */
export interface MeetingSiteConfig {
  name: string;
  hostPatterns: RegExp[];
  /** 当前实时字幕（caption）文本元素选择器 */
  subtitleSelector: string;
  /** 字幕容器（注入覆盖层锚点） */
  containerSelector: string;
  /** 转写/字幕面板（滚动容器内的条目列表） */
  panelSelector: string;
  /** 面板内单条字幕条目 */
  entrySelector: string;
  /** 滚动容器（滚动跟随锚定） */
  scrollSelector: string;
  isMeeting: true;
}

const MEETING_SITES: MeetingSiteConfig[] = [
  {
    name: 'Zoom',
    hostPatterns: [/zoom\.us/],
    // 实时字幕（Zoom Web Client 的 caption 区域）
    subtitleSelector:
      '.caption-view .caption-line, [class*="caption"] [class*="line"], [data-testid="caption"] div',
    containerSelector: '.meeting-client, .layout-wrapper, body',
    // 字幕/转写面板条目（带 role 的 div 列表）
    panelSelector:
      '[role="list"][aria-label*="transcript" i], [role="list"][aria-label*="字幕" i], .transcript-panel [role="list"], .cc-transcript',
    entrySelector: '[role="listitem"], .transcript-line, [class*="transcript"] > div',
    scrollSelector: '.transcript-panel [role="region"], .cc-transcript, [role="list"]',
    isMeeting: true,
  },
  {
    name: 'Google Meet',
    hostPatterns: [/meet\.google\.com/],
    // 实时字幕：Meet 的字幕块在 side panel / 底部 caption 容器内
    subtitleSelector:
      'div[aria-live="polite"] .iOzktd, .nMcdBd .iOzktd, [data-part-of="caption"] span, div[jscontroller] .VfPpkd-v0iGne',
    containerSelector: '.c8mSod, .p2hjYe, body',
    // 转写面板（side panel 的字幕记录，role=list 的 div 列表）
    panelSelector:
      '[role="list"][aria-label*="字幕" i], [role="list"][aria-label*="caption" i], [role="list"][aria-label*="transcript" i], .z38b6',
    entrySelector: '[role="listitem"]',
    scrollSelector: '[role="list"]',
    isMeeting: true,
  },
  {
    name: 'Microsoft Teams',
    hostPatterns: [/teams\.microsoft\.com/, /teams\.live\.com/],
    // 实时字幕（Teams 会议字幕行）
    subtitleSelector:
      '[data-tid="closed-caption"] div, [data-tid="subtitle-line"], .ts-caption-line, [class*="caption"] [class*="line"]',
    containerSelector: '[data-tid="app-canvas"], .app-canvas, body',
    // 会议转写面板
    panelSelector:
      '[data-tid="transcript-container"] [role="list"], [role="list"][aria-label*="transcript" i], [role="list"][aria-label*="记录" i]',
    entrySelector: '[role="listitem"]',
    scrollSelector: '[data-tid="transcript-container"] [role="region"], [role="list"]',
    isMeeting: true,
  },
];

/** 检测当前页面是否是会议平台（返回配置或 null） */
export function detectMeetingSite(hostname: string): MeetingSiteConfig | null {
  for (const site of MEETING_SITES) {
    if (site.hostPatterns.some(p => p.test(hostname))) return site;
  }
  return null;
}

/**
 * 滚动跟随锚定：转写面板插入新内容后保持用户视口。
 * 用户原本贴着底部 → 插入后继续贴底；用户往上翻阅历史 → 不打扰。
 */
export function shouldStickToBottom(scrollEl: Element | null): boolean {
  if (!scrollEl) return true;
  const el = scrollEl as HTMLElement;
  const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
  return distanceToBottom <= 48;
}

/** 滚动到底部 */
export function stickToBottom(scrollEl: Element | null): void {
  if (!scrollEl) return;
  const el = scrollEl as HTMLElement;
  el.scrollTop = el.scrollHeight;
}
