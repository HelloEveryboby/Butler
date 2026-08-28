/* ============================================================
   微软免费翻译（Azure Cognitive Services 免费层）
   ============================================================ */

import { BaseProvider } from './base';
import { LangCode, ProviderId } from '../../utils/types';

export class BingFreeProvider extends BaseProvider {
  readonly id: ProviderId = 'bing-free';
  readonly name = '微软免费翻译';

  private tokenUrl = 'https://edge.microsoft.com/translate/auth';
  private apiUrl = 'https://api-edge.cognitive.microsofttranslator.com/translate';
  private cachedToken: string | null = null;
  private tokenExpiry = 0;

  private async getToken(): Promise<string> {
    if (this.cachedToken && Date.now() < this.tokenExpiry) {
      return this.cachedToken;
    }
    const resp = await fetch(this.tokenUrl);
    if (!resp.ok) throw new Error(`Bing token HTTP ${resp.status}`);
    this.cachedToken = await resp.text();
    this.tokenExpiry = Date.now() + 8 * 60 * 1000; // 8 分钟有效
    return this.cachedToken;
  }

  async translate(text: string, from: LangCode, to: LangCode): Promise<string> {
    const token = await this.getToken();
    const url = `${this.apiUrl}?api-version=3.0&from=${from}&to=${to}`;

    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify([{ Text: text }]),
    });

    if (!resp.ok) throw new Error(`Bing translate HTTP ${resp.status}`);
    const data = await resp.json();
    return data?.[0]?.translations?.[0]?.text ?? '';
  }

  async translateBatch(texts: string[], from: LangCode, to: LangCode): Promise<string[]> {
    const token = await this.getToken();
    const url = `${this.apiUrl}?api-version=3.0&from=${from}&to=${to}`;

    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(texts.map(t => ({ Text: t }))),
    });

    if (!resp.ok) throw new Error(`Bing batch translate HTTP ${resp.status}`);
    const data = await resp.json();
    return data.map((item: any) => item?.translations?.[0]?.text ?? '');
  }
}
