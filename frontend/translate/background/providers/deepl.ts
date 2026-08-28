/* ============================================================
   DeepL 翻译 API
   ============================================================ */

import { BaseProvider } from './base';
import { LangCode, ProviderId, ProviderConfig } from '../../utils/types';

export class DeepLProvider extends BaseProvider {
  readonly id: ProviderId = 'deepl';
  readonly name = 'DeepL';

  private apiKey: string;
  private useFreeApi: boolean;

  constructor(config: ProviderConfig) {
    super();
    this.apiKey = config.apiKey || '';
    // 免费版和付费版 endpoint 不同
    this.useFreeApi = !config.endpoint || config.endpoint.includes('free');
  }

  private get endpoint(): string {
    return this.useFreeApi
      ? 'https://api-free.deepl.com/v2/translate'
      : 'https://api.deepl.com/v2/translate';
  }

  async translate(text: string, from: LangCode, to: LangCode): Promise<string> {
    const params = new URLSearchParams();
    params.append('text', text);
    params.append('target_lang', to.replace('-', '_').split('_')[0].toUpperCase());
    if (from !== 'auto') {
      params.append('source_lang', from.replace('-', '_').split('_')[0].toUpperCase());
    }

    const resp = await fetch(this.endpoint, {
      method: 'POST',
      headers: {
        'Authorization': `DeepL-Auth-Key ${this.apiKey}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params.toString(),
    });

    if (!resp.ok) throw new Error(`DeepL HTTP ${resp.status}`);
    const data = await resp.json();
    return data?.translations?.[0]?.text ?? '';
  }

  async translateBatch(texts: string[], from: LangCode, to: LangCode): Promise<string[]> {
    const params = new URLSearchParams();
    for (const text of texts) {
      params.append('text', text);
    }
    params.append('target_lang', to.replace('-', '_').split('_')[0].toUpperCase());
    if (from !== 'auto') {
      params.append('source_lang', from.replace('-', '_').split('_')[0].toUpperCase());
    }

    const resp = await fetch(this.endpoint, {
      method: 'POST',
      headers: {
        'Authorization': `DeepL-Auth-Key ${this.apiKey}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params.toString(),
    });

    if (!resp.ok) throw new Error(`DeepL batch HTTP ${resp.status}`);
    const data = await resp.json();
    return data.translations?.map((t: any) => t.text) ?? [];
  }
}
