/* ============================================================
   Butler 本地翻译（通过 WebSocket 调用 Butler Python 后端）
   完全离线，隐私安全
   ============================================================ */

import { BaseProvider } from './base';
import { LangCode, ProviderId } from '../../utils/types';

export class ButlerBHLProvider extends BaseProvider {
  readonly id: ProviderId = 'butler-bhl';
  readonly name = 'Butler 本地翻译';

  private wsUrl: string;
  private ws: WebSocket | null = null;
  private pending = new Map<string, { resolve: (v: string) => void; reject: (e: Error) => void }>();

  constructor(wsUrl = 'ws://127.0.0.1:8765') {
    super();
    this.wsUrl = wsUrl;
  }

  private ensureConnection(): Promise<WebSocket> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return Promise.resolve(this.ws);
    }

    return new Promise((resolve, reject) => {
      const ws = new WebSocket(this.wsUrl);
      ws.onopen = () => { this.ws = ws; resolve(ws); };
      ws.onerror = () => reject(new Error('Butler WebSocket connection failed'));
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.action === 'translate.result' && msg.payload?.id) {
            const pending = this.pending.get(msg.payload.id);
            if (pending) {
              this.pending.delete(msg.payload.id);
              pending.resolve(msg.payload.translated);
            }
          }
        } catch {}
      };
      ws.onclose = () => { this.ws = null; };
    });
  }

  async translate(text: string, from: LangCode, to: LangCode): Promise<string> {
    const ws = await this.ensureConnection();
    const id = crypto.randomUUID();

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error('Butler BHL translate timeout'));
      }, 30000);

      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v); },
        reject: (e) => { clearTimeout(timer); reject(e); },
      });

      ws.send(JSON.stringify({
        action: 'translate.text',
        payload: { id, text, from, to },
      }));
    });
  }
}
