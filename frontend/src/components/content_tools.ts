/**
 * 内容工具（朗读 / 文档扫描 / 文件版本）的前端入口。
 *
 * 统一走 PyWebViewBridge.callSkill，与 CLI、TUI、REST 共用同一套后端实现。
 * 所有 DOM 写入均使用 textContent，避免 innerHTML。
 */

import { PyWebViewBridge } from '../core/bridge';

type Payload = Record<string, any>;

export interface ReadingSegment {
  index: number;
  speaker: string;
  text: string;
  kind: string;
}

export class ContentTools {
  /**
   * 统一调用核心能力（reading/scanner/versioning/commands/dsh）。
   * 优先走 pywebview 的 call_capability；旧后端回退到 call_skill。
   */
  private static async call(
    capability: string,
    action: string,
    payload: Payload = {},
  ): Promise<Payload> {
    const api = (window as any).pywebview?.api;
    if (api && typeof api.call_capability === 'function') {
      return api.call_capability(capability, action, payload);
    }
    return PyWebViewBridge.callSkill<Payload>(capability, action, payload);
  }

  // ── 朗读 ──────────────────────────────────────────────

  static async read(source: string, options: Payload = {}): Promise<Payload> {
    return ContentTools.call('reading', 'play', { source, ...options });
  }

  static async readText(text: string, name = '内容'): Promise<Payload> {
    return ContentTools.call('reading', 'play', { text, name });
  }

  static async pauseReading(): Promise<Payload> {
    return ContentTools.call('reading', 'pause');
  }

  static async resumeReading(): Promise<Payload> {
    return ContentTools.call('reading', 'resume');
  }

  static async stopReading(): Promise<Payload> {
    return ContentTools.call('reading', 'stop');
  }

  static async readingStatus(): Promise<Payload> {
    return ContentTools.call('reading', 'status');
  }

  static async explainTokens(text: string): Promise<Payload> {
    return ContentTools.call('reading', 'explain_tokens', { text });
  }

  /**
   * 渲染朗读文本并高亮当前句（颜色标框）。
   * 每句一个 span，靠 background/outline 标出朗读位置。
   */
  static renderReading(
    container: HTMLElement,
    segments: ReadingSegment[],
    currentIndex = -1,
  ): void {
    container.textContent = '';
    segments.forEach((segment) => {
      const span = document.createElement('span');
      span.dataset.index = String(segment.index);
      span.textContent = segment.kind === 'dialogue'
        ? `${segment.speaker}：${segment.text}`
        : segment.text;
      span.style.display = 'inline';
      span.style.padding = '1px 2px';
      if (segment.index === currentIndex) {
        span.style.background = 'rgba(255, 214, 0, 0.35)';
        span.style.outline = '2px solid rgba(255, 170, 0, 0.9)';
        span.style.borderRadius = '3px';
      }
      container.appendChild(span);
      container.appendChild(document.createTextNode('\n'));
    });
  }

  // ── 文档扫描 ──────────────────────────────────────────

  static async scan(
    paths: string[],
    out = 'scan_output.pdf',
    options: Payload = {},
  ): Promise<Payload> {
    return ContentTools.call('scanner', 'scan', {
      paths,
      out,
      ...options,
    });
  }

  static async scanCamera(out = 'scan_camera.pdf', options: Payload = {}): Promise<Payload> {
    return ContentTools.call('scanner', 'camera', { out, ...options });
  }

  static async convertFile(path: string, to: string): Promise<Payload> {
    return ContentTools.call('scanner', 'convert', { path, to });
  }

  // ── 文件版本 ──────────────────────────────────────────

  static async versionSnapshot(path: string, message = ''): Promise<Payload> {
    return ContentTools.call('versioning', 'snapshot', { path, message });
  }

  static async versionLog(path: string): Promise<Payload> {
    return ContentTools.call('versioning', 'list', { path });
  }

  static async versionDiff(path: string): Promise<Payload> {
    return ContentTools.call('versioning', 'diff', { path });
  }

  static async versionRestore(path: string, rev: string): Promise<Payload> {
    return ContentTools.call('versioning', 'restore', { path, rev });
  }
}
