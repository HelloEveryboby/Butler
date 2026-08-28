/* ============================================================
   Provider 基类接口
   ============================================================ */

import { TranslationProvider, LangCode, ProviderId } from '../types';

export abstract class BaseProvider implements TranslationProvider {
  abstract readonly id: ProviderId;
  abstract readonly name: string;

  abstract translate(text: string, from: LangCode, to: LangCode): Promise<string>;

  /** 默认批量：逐条翻译。有批量 API 的 Provider 应覆写此方法 */
  async translateBatch(texts: string[], from: LangCode, to: LangCode): Promise<string[]> {
    const results: string[] = [];
    for (const text of texts) {
      results.push(await this.translate(text, from, to));
    }
    return results;
  }
}
