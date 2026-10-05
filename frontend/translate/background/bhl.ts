/* ============================================================
   Butler BHL WebSocket 客户端（Background 侧）
   ------------------------------------------------------------
   与 package/document/translate_system/server.py 的协议对齐：
     请求  {"action":"translate.text",  "payload":{"id","text","from","to"}}
     响应  {"action":"translate.result","payload":{"id","translated"}}
     请求  {"action":"translate.image", "payload":{"id","base64","from","to"}}
     响应  {"action":"translate.image.result","payload":{"id","text","translated"}}
     请求  {"action":"glossary.list"}    响应  {"action":"glossary.data","payload":{"terms":[...]}}
     请求  {"action":"glossary.add", "payload":{"source","target"}}   响应  {"action":"ok"}
     请求  {"action":"export.pdf",  "payload":{"id","pdfBase64","filename","to"}}
       —— 后端实现则返回 {"action":"export.pdf.result","payload":{"id","dataUrl","filename"}}；
          未实现则返回 {"action":"error", ...}，前端如实报错，绝不假装成功。
   ============================================================ */

export interface BhlImageResult {
  /** OCR 出的原文 */
  text: string;
  /** 译文 */
  translated: string;
}

export interface BhlPdfExportResult {
  /** 导出结果文件（data URL） */
  dataUrl: string;
  filename: string;
}

export interface BhlGlossaryTerm {
  source: string;
  target: string;
}

type Pending = {
  resolve: (v: any) => void;
  reject: (e: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};

export class ButlerBhlClient {
  private wsUrl: string;
  private timeoutMs: number;
  private ws: WebSocket | null = null;
  private connecting: Promise<WebSocket> | null = null;
  /** 按请求 id 匹配的等待队列 */
  private pendingById = new Map<string, Pending>();
  /** 按响应 action 匹配的等待队列（glossary.data / ok 等不带 id 的响应） */
  private pendingByAction = new Map<string, Pending[]>();

  constructor(wsUrl: string, timeoutMs = 30000) {
    this.wsUrl = wsUrl;
    this.timeoutMs = timeoutMs;
  }

  /** 当前后端是否可达（尽力探测，不抛异常） */
  async isAvailable(): Promise<boolean> {
    try {
      await this.ensureConnection();
      return true;
    } catch {
      return false;
    }
  }

  private ensureConnection(): Promise<WebSocket> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return Promise.resolve(this.ws);
    }
    if (this.connecting) return this.connecting;

    this.connecting = new Promise<WebSocket>((resolve, reject) => {
      let ws: WebSocket;
      try {
        ws = new WebSocket(this.wsUrl);
      } catch (err) {
        this.connecting = null;
        reject(new Error(`Butler 后端地址无效: ${this.wsUrl} (${err})`));
        return;
      }

      const onFail = (why: string) => {
        this.connecting = null;
        ws.close();
        reject(new Error(`无法连接 Butler 后端 ${this.wsUrl}：${why}`));
      };

      ws.onopen = () => {
        this.connecting = null;
        this.ws = ws;
        resolve(ws);
      };
      ws.onerror = () => onFail('连接出错');
      ws.onclose = () => {
        this.ws = null;
        this.rejectAll(new Error('Butler 后端连接已关闭'));
      };
      ws.onmessage = (event) => {
        this.handleFrame(String(event.data));
      };

      // 连接超时
      setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) onFail('连接超时');
      }, Math.min(this.timeoutMs, 5000));
    });

    return this.connecting;
  }

  /** 帧分发：id 匹配优先，其次 action 匹配；error 帧如实拒绝 */
  private handleFrame(raw: string): void {
    let msg: any;
    try {
      msg = JSON.parse(raw);
    } catch {
      return; // 忽略非 JSON 帧
    }
    const action: string | undefined = msg?.action;
    const id: string | undefined = msg?.payload?.id;

    // 1. id 匹配
    if (id && this.pendingById.has(id)) {
      const p = this.pendingById.get(id)!;
      this.pendingById.delete(id);
      clearTimeout(p.timer);
      // translate.error / export.pdf.result 等错误帧如实拒绝
      if (typeof action === 'string' && action.endsWith('.error')) {
        p.reject(new Error(String(msg?.payload?.message || action)));
      } else {
        p.resolve(msg.payload);
      }
      return;
    }

    // 2. 错误帧：拒绝所有等待中的请求（不假装成功）
    if (action === 'error' || (typeof action === 'string' && action.endsWith('.error'))) {
      this.rejectAll(new Error(String(msg?.payload?.message || `Butler 后端错误（${action}）`)));
      return;
    }

    // 3. action 匹配（glossary.data / ok 等不带 id 的响应）
    if (action) {
      const queue = this.pendingByAction.get(action);
      if (queue && queue.length > 0) {
        const p = queue.shift()!;
        clearTimeout(p.timer);
        p.resolve(msg.payload ?? {});
      }
    }
  }

  private rejectAll(err: Error): void {
    for (const [, p] of this.pendingById) {
      clearTimeout(p.timer);
      p.reject(err);
    }
    this.pendingById.clear();
    for (const [, queue] of this.pendingByAction) {
      for (const p of queue) {
        clearTimeout(p.timer);
        p.reject(err);
      }
    }
    this.pendingByAction.clear();
  }

  /** 发一个请求并等待对应 id 的响应 */
  private async request(action: string, payload: Record<string, unknown>): Promise<any> {
    const ws = await this.ensureConnection();
    const id = crypto.randomUUID();

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingById.delete(id);
        reject(new Error(`Butler 后端响应超时（${action}）`));
      }, this.timeoutMs);

      this.pendingById.set(id, { resolve, reject, timer });
      ws.send(JSON.stringify({ action, payload: { id, ...payload } }));
    });
  }

  /** 发一个请求并按响应 action 名匹配（后端不回 id 的老接口） */
  private async requestByAction(
    action: string,
    payload: Record<string, unknown>,
    expectedResponseAction: string
  ): Promise<any> {
    const ws = await this.ensureConnection();

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        const queue = this.pendingByAction.get(expectedResponseAction) || [];
        const idx = queue.findIndex(p => p.timer === timer);
        if (idx >= 0) queue.splice(idx, 1);
        reject(new Error(`Butler 后端响应超时（${action}）`));
      }, this.timeoutMs);

      const queue = this.pendingByAction.get(expectedResponseAction) || [];
      queue.push({ resolve, reject, timer });
      this.pendingByAction.set(expectedResponseAction, queue);
      ws.send(JSON.stringify({ action, payload }));
    });
  }

  /** 文本翻译 */
  async translateText(text: string, from: string, to: string): Promise<string> {
    const res = await this.request('translate.text', { text, from, to });
    return String(res?.translated ?? '');
  }

  /** 图片翻译（OCR + 翻译） */
  async translateImage(base64: string, from: string, to: string): Promise<BhlImageResult> {
    const res = await this.request('translate.image', { base64, from, to });
    return {
      text: String(res?.text ?? ''),
      translated: String(res?.translated ?? ''),
    };
  }

  /**
   * 双语 PDF 导出（转发给 Butler 后端 CLI）。
   * 后端未实现 export.pdf 时抛错，由调用方给出明确提示，绝不假装成功。
   */
  async exportPdf(pdfBase64: string, filename: string, to: string): Promise<BhlPdfExportResult> {
    const res = await this.request('export.pdf', { pdfBase64, filename, to });
    const dataUrl = String(res?.dataUrl ?? '');
    if (!dataUrl) throw new Error('Butler 后端未返回导出文件（dataUrl 为空）');
    return { dataUrl, filename: String(res?.filename || filename.replace(/\.pdf$/i, '_bilingual.pdf')) };
  }

  /** 术语表：拉取后端全量术语 */
  async glossaryList(): Promise<BhlGlossaryTerm[]> {
    const res = await this.requestByAction('glossary.list', {}, 'glossary.data');
    const terms = res?.terms;
    if (!Array.isArray(terms)) return [];
    return terms
      .filter((t: any) => t && t.source && t.target)
      .map((t: any) => ({ source: String(t.source), target: String(t.target) }));
  }

  /** 术语表：向后端新增一条术语 */
  async glossaryAdd(source: string, target: string): Promise<void> {
    await this.requestByAction('glossary.add', { source, target }, 'ok');
  }

  close(): void {
    this.ws?.close();
    this.ws = null;
  }
}
