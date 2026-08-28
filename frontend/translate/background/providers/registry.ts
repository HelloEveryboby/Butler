/* ============================================================
   Provider 注册表 — 根据配置创建 Provider 实例
   ============================================================ */

import { TranslationProvider, ProviderConfig, ProviderId } from '../../utils/types';
import { GoogleFreeProvider } from './google-free';
import { BingFreeProvider } from './bing-free';
import { OpenAICompatProvider, DeepSeekProvider } from './openai-compat';
import { DeepLProvider } from './deepl';
import { BaiduProvider } from './baidu';
import { ButlerBHLProvider } from './butler-bhl';

export function createProvider(config: ProviderConfig): TranslationProvider {
  switch (config.type) {
    case 'google-free':
      return new GoogleFreeProvider();
    case 'bing-free':
      return new BingFreeProvider();
    case 'deepseek':
    case 'openai-compat':
      return new OpenAICompatProvider(config);
    case 'deepl':
      return new DeepLProvider(config);
    case 'baidu':
      return new BaiduProvider(config);
    case 'butler-bhl':
      return new ButlerBHLProvider(config.endpoint);
    default:
      throw new Error(`Unknown provider type: ${config.type}`);
  }
}

export function createProviderWithFallback(
  providers: TranslationProvider[]
): TranslationProvider {
  if (providers.length === 1) return providers[0];

  return {
    id: providers[0].id,
    name: `${providers[0].name}（含降级）`,

    async translate(text, from, to) {
      let lastError: Error | null = null;
      for (const provider of providers) {
        try {
          return await provider.translate(text, from, to);
        } catch (err) {
          lastError = err as Error;
          console.warn(`[ButlerTranslate] Provider ${provider.name} failed, trying next...`);
        }
      }
      throw lastError || new Error('All providers failed');
    },

    async translateBatch(texts, from, to) {
      let lastError: Error | null = null;
      for (const provider of providers) {
        try {
          if (provider.translateBatch) {
            return await provider.translateBatch(texts, from, to);
          }
          // 逐条回退
          const results: string[] = [];
          for (const t of texts) {
            results.push(await provider.translate(t, from, to));
          }
          return results;
        } catch (err) {
          lastError = err as Error;
          console.warn(`[ButlerTranslate] Batch provider ${provider.name} failed, trying next...`);
        }
      }
      throw lastError || new Error('All batch providers failed');
    },
  };
}
