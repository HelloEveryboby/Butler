/* ============================================================
   Butler Translate — 默认配置
   与 Butler 主系统保持一致：默认使用 DeepSeek
   ============================================================ */

import { TranslateConfig, ProviderConfig } from './types';

/** Butler 默认翻译源：DeepSeek（与主系统一致） */
export const DEFAULT_PROVIDERS: ProviderConfig[] = [
  {
    id: 'deepseek-default',
    type: 'deepseek',
    name: 'DeepSeek（默认）',
    endpoint: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
    enabled: true,
  },
  {
    id: 'google-free',
    type: 'google-free',
    name: 'Google 免费翻译',
    enabled: true,
  },
  {
    id: 'bing-free',
    type: 'bing-free',
    name: '微软免费翻译',
    enabled: true,
  },
];

export const DEFAULT_CONFIG: TranslateConfig = {
  activeProviderId: 'deepseek-default',
  providers: DEFAULT_PROVIDERS,
  targetLang: 'zh-CN',
  autoTranslate: false,
  displayMode: 'bilingual',
  triggerKey: 'Alt+Q',
  inputTranslateKey: 'Ctrl+Enter',
  screenshotKey: 'Alt+S',
  theme: 'underline',
  fontSize: 'inherit',
  fontWeight: 'normal',
  colorFollowOriginal: true,
  customColor: '#666',
  excludeSites: [],
  excludeSelectors: ['pre', 'code', 'script', 'style', 'noscript', 'svg', 'canvas'],
  cacheEnabled: true,
  cacheMaxSize: 2000,
  butlerBackendUrl: 'ws://127.0.0.1:8765',
  fallbackChain: ['deepseek-default', 'google-free', 'bing-free'],
};
