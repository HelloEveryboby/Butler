/* ============================================================
   Butler Translate — 类型定义
   ============================================================ */

// ---------- 语言 ----------
export type LangCode = string; // 'zh-CN' | 'en' | 'ja' | 'ko' | 'fr' | 'de' | ...

export interface LangItem {
  code: LangCode;
  name: string;       // 中文名
  nameEn: string;     // 英文名
}

// ---------- 翻译 Provider ----------
export type ProviderId =
  | 'deepseek'
  | 'google-free'
  | 'bing-free'
  | 'deepl'
  | 'baidu'
  | 'openai-compat'
  | 'butler-bhl';

export interface ProviderConfig {
  id: string;              // 唯一标识（用户添加多个 openai-compat 时用 name 区分）
  type: ProviderId;        //  provider 类型
  name: string;            // 显示名称
  endpoint?: string;       // API 地址
  apiKey?: string;         // API Key
  model?: string;          // 模型名
  prompt?: string;         // 自定义翻译提示词
  enabled: boolean;
}

export interface TranslationResult {
  original: string;
  translated: string;
  provider: string;
  from?: LangCode;
  to?: LangCode;
}

// ---------- 翻译 Provider 接口 ----------
export interface TranslationProvider {
  readonly id: ProviderId;
  readonly name: string;

  /** 翻译单段文本 */
  translate(text: string, from: LangCode, to: LangCode): Promise<string>;

  /** 批量翻译（默认逐条，子类可覆写为批量 API） */
  translateBatch?(texts: string[], from: LangCode, to: LangCode): Promise<string[]>;
}

// ---------- 配置 ----------
export interface TranslateConfig {
  // 当前使用的翻译源
  activeProviderId: string;

  // 所有已配置的翻译源列表
  providers: ProviderConfig[];

  // 翻译行为
  targetLang: LangCode;
  autoTranslate: boolean;         // 页面加载后自动翻译
  displayMode: 'bilingual' | 'translation-only' | 'hover';
  triggerKey: string;             // 全文翻译快捷键
  inputTranslateKey: string;      // 输入框翻译快捷键
  screenshotKey: string;          // 截图翻译快捷键

  // 样式
  theme: 'underline' | 'highlight' | 'background' | 'bubble';
  fontSize: string;
  fontWeight: 'normal' | 'bold';
  colorFollowOriginal: boolean;
  customColor: string;

  // 排除
  excludeSites: string[];
  excludeSelectors: string[];

  // 缓存
  cacheEnabled: boolean;
  cacheMaxSize: number;

  // Butler 后端
  butlerBackendUrl: string;

  // 降级链
  fallbackChain: string[];  // provider id 列表，按优先级排列
}

// ---------- DOM 分段 ----------
export interface TextSegment {
  id: string;
  elements: Node[];          // 原始文本节点
  originalText: string;
  parentElement: Element;    // 用于定位注入位置
  isInline: boolean;
}

// ---------- 消息协议 ----------
export type MsgType =
  | { type: 'TRANSLATE'; texts: string[]; from?: LangCode; to: LangCode; providerId?: string }
  | { type: 'TRANSLATE_SELECTION'; text: string }
  | { type: 'TRANSLATE_IMAGE'; base64: string }
  | { type: 'GET_CONFIG' }
  | { type: 'SET_CONFIG'; config: Partial<TranslateConfig> }
  | { type: 'GET_PROVIDERS' }
  | { type: 'ADD_PROVIDER'; provider: ProviderConfig }
  | { type: 'UPDATE_PROVIDER'; id: string; patch: Partial<ProviderConfig> }
  | { type: 'DELETE_PROVIDER'; id: string }
  | { type: 'TEST_PROVIDER'; provider: ProviderConfig };

export type MsgResponse =
  | { type: 'TRANSLATE_RESULT'; results: TranslationResult[] }
  | { type: 'TRANSLATE_ERROR'; error: string; fallbackProvider?: string }
  | { type: 'CONFIG'; config: TranslateConfig }
  | { type: 'PROVIDERS'; providers: ProviderConfig[] }
  | { type: 'TEST_RESULT'; success: boolean; message: string }
  | { type: 'IMAGE_TRANSLATE_RESULT'; original: string; translated: string }
  | { type: 'OK' };

// ---------- 站点规则 ----------
export interface SiteRule {
  domain: string | RegExp;
  selectors?: string[];      // 要翻译的选择器
  exclude?: string[];        // 排除的选择器
  insertPosition?: 'afterend' | 'beforeend' | 'replace';
}
