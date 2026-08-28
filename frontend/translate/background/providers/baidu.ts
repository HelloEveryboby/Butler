/* ============================================================
   百度翻译 API
   ============================================================ */

import { BaseProvider } from './base';
import { LangCode, ProviderId, ProviderConfig } from '../../utils/types';

export class BaiduProvider extends BaseProvider {
  readonly id: ProviderId = 'baidu';
  readonly name = '百度翻译';

  private appId: string;
  private secretKey: string;

  constructor(config: ProviderConfig) {
    super();
    // apiKey 格式: "appId:secretKey"
    const parts = (config.apiKey || '').split(':');
    this.appId = parts[0] || '';
    this.secretKey = parts[1] || '';
  }

  private async md5(str: string): Promise<string> {
    const encoder = new TextEncoder();
    const data = encoder.encode(str);
    const hash = await crypto.subtle.digest('MD5', data);
    return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  async translate(text: string, from: LangCode, to: LangCode): Promise<string> {
    const salt = Date.now().toString();
    const sign = await this.md5(this.appId + text + salt + this.secretKey);

    const params = new URLSearchParams({
      q: text,
      from: from === 'zh-CN' ? 'zh' : from,
      to: to === 'zh-CN' ? 'zh' : to,
      appid: this.appId,
      salt,
      sign,
    });

    const resp = await fetch(`https://fanyi-api.baidu.com/api/trans/vip/translate?${params}`);
    if (!resp.ok) throw new Error(`Baidu translate HTTP ${resp.status}`);

    const data = await resp.json();
    if (data.error_code) throw new Error(`Baidu: ${data.error_msg} (${data.error_code})`);

    return data?.trans_result?.map((r: any) => r.dst).join('\n') ?? '';
  }
}
