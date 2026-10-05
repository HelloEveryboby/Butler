/* ============================================================
   Butler Translate — 默认配置
   与 Butler 主系统保持一致：默认使用 DeepSeek
   ============================================================ */

import { TranslateConfig, ProviderConfig } from './types';
import { BUILTIN_PRESETS } from './presets';

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
  bilingualLayout: 'stacked',
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
  glossary: [],
  historyEnabled: true,
  historyMaxSize: 500,
  butlerBackendUrl: 'ws://127.0.0.1:8765',
  fallbackChain: ['deepseek-default', 'google-free', 'bing-free'],

  // 悬停翻译：按住 Alt 才显示整段译文，松开即消失
  hoverTriggerKey: 'Alt',

  // AI 上下文翻译（页面摘要 + 术语一致性）
  ctxEnabled: true,

  // AI 专家 / 行业身份预设
  presets: BUILTIN_PRESETS,
  activePresetId: 'general',
  sitePresetBindings: [],

  // 输入框翻译
  inputTripleSpace: true,
  inputDirection: 'auto',

  // 用户自定义站点规则
  customSiteRules: [],
};
