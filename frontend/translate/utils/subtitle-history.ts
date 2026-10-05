/* ============================================================
   字幕翻译历史 — 用于双语 SRT/VTT 导出
   ------------------------------------------------------------
   来源：
   1. 文档字幕翻译（SRT/VTT 文件）：带真实时间轴
   2. 实时字幕翻译（会议 / 视频）：按会话记录，时间轴为近似值
   存储于 chrome.storage.local，保留最近若干会话。
   ============================================================ */

import { SubtitleCue, makeCue, bilingualCueText } from './subtitle-io';

const SESSIONS_KEY = 'butler_subtitle_sessions';
const MAX_SESSIONS = 10;

/** 字幕翻译会话中的一条记录 */
export interface SubtitlePair {
  startMs: number;
  endMs: number;
  original: string;
  translated: string;
}

/** 一次字幕翻译会话 */
export interface SubtitleSession {
  id: string;
  ts: number;
  /** 来源描述（文件名 / 站点名） */
  title: string;
  targetLang: string;
  /** true = 文档翻译（时间轴精确）；false = 实时字幕（时间轴近似） */
  preciseTiming: boolean;
  pairs: SubtitlePair[];
}

/** 保存一个会话（覆盖同 id，超上限淘汰最旧） */
export async function saveSubtitleSession(session: SubtitleSession): Promise<void> {
  try {
    const sessions = await loadSubtitleSessions();
    const idx = sessions.findIndex(s => s.id === session.id);
    if (idx >= 0) sessions[idx] = session;
    else sessions.push(session);
    const trimmed = sessions.slice(-MAX_SESSIONS);
    await chrome.storage.local.set({ [SESSIONS_KEY]: trimmed });
  } catch (e) {
    console.warn('[ButlerTranslate] Subtitle session save failed:', e);
  }
}

/** 读取全部会话（新的在后） */
export async function loadSubtitleSessions(): Promise<SubtitleSession[]> {
  try {
    const r = await chrome.storage.local.get(SESSIONS_KEY);
    return (r[SESSIONS_KEY] as SubtitleSession[]) || [];
  } catch {
    return [];
  }
}

/** 最近一个会话 */
export async function getLatestSubtitleSession(): Promise<SubtitleSession | null> {
  const sessions = await loadSubtitleSessions();
  return sessions.length ? sessions[sessions.length - 1] : null;
}

/**
 * 会话 → 双语 cue 列表（原文 + 译文两行，时间轴不动）
 */
export function sessionToBilingualCues(session: SubtitleSession): SubtitleCue[] {
  return session.pairs.map((p, i) => {
    const cue = makeCue(i + 1, p.startMs, p.endMs, '');
    return { ...cue, text: bilingualCueText(p.original, p.translated) };
  });
}

/** 实时字幕的近似时间轴：按字数估算每条时长 */
export function estimateCueDuration(text: string): number {
  return Math.min(8000, Math.max(2000, text.length * 80));
}
