/* ============================================================
   Google 免费翻译（抓取 translate.googleapis.com）
   无需 API Key，开箱即用
   ============================================================ */

import { BaseProvider } from './base';
import { LangCode, ProviderId } from '../../utils/types';

export class GoogleFreeProvider extends BaseProvider {
  readonly id: ProviderId = 'google-free';
  readonly name = 'Google 免费翻译';

  async translate(text: string, from: LangCode, to: LangCode): Promise<string> {
    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=${from}&tl=${to}&dt=t&q=${encodeURIComponent(text)}`;

    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`Google translate HTTP ${resp.status}`);

    const data = await resp.json();
    // data[0] 是翻译结果数组，每项 [translated, original]
    if (!data?.[0]) throw new Error('Google translate: empty result');

    return data[0].map((item: string[]) => item[0]).join('');
  }

  async translateBatch(texts: string[], from: LangCode, to: LangCode): Promise<string[]> {
    // Google 免费 API 不支持真正的批量，用 \n\n 分隔合并
    const separator = '\n\n';
    const joined = texts.join(separator);
    const translated = await this.translate(joined, from, to);
    // 按分隔符拆回（Google 可能保留 \n\n）
    const parts = translated.split(/\n\n+/);
    // 如果拆分数量不对，退化为逐条
    if (parts.length !== texts.length) {
      return super.translateBatch!(texts, from, to);
    }
    return parts;
  }
}
