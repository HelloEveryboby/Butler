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

// ---------- 术语表 ----------
export interface GlossaryEntry {
  source: string;
  target: string;
}

// ---------- 翻译历史 ----------
export interface HistoryEntry {
  original: string;
  translated: string;
  from?: LangCode;
  to?: LangCode;
  provider: string;
  favorite?: boolean;
  ts: number;
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

// ---------- AI 页面上下文（摘要 + 术语候选） ----------
export interface PageContext {
  summary: string;           // 页面内容摘要
  terms: GlossaryEntry[];    // 本页术语候选（原文 → 建议译法）
}

// ---------- AI 专家 / 行业身份预设 ----------
export interface PresetRules {
  numbers: string;   // 数字处理规则
  units: string;     // 单位处理规则
  code: string;      // 代码 / 专有名词处理规则
}

export interface PresetTemplate {
  id: string;
  name: string;
  identity: string;      // 身份设定
  tone: string;          // 语气
  termStyle: string;     // 术语倾向
  rules: PresetRules;
  builtin?: boolean;     // 内置预设（可编辑副本，不可删除）
}

/** 按站点绑定默认预设 */
export interface SitePresetBinding {
  pattern: string;   // 域名片段（hostname.includes）或 /regex/ 字符串
  presetId: string;
}

// ---------- 翻译选项（LLM 类 Provider 使用） ----------
export interface TranslateOptions {
  /** 术语强制约束（进 prompt，事后仍由 applyGlossary 兜底） */
  glossary?: GlossaryEntry[];
  /** 页面上下文（摘要 + 术语） */
  context?: PageContext;
  /** 行业身份预设 */
  preset?: PresetTemplate;
}

// ---------- 翻译 Provider 接口 ----------
export interface TranslationProvider {
  readonly id: ProviderId;
  readonly name: string;

  /** 翻译单段文本 */
  translate(text: string, from: LangCode, to: LangCode, opts?: TranslateOptions): Promise<string>;

  /** 批量翻译（默认逐条，子类可覆写为批量 API） */
  translateBatch?(texts: string[], from: LangCode, to: LangCode, opts?: TranslateOptions): Promise<string[]>;
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
  bilingualLayout: 'stacked' | 'columns';  // 双语排版：堆叠 / 双栏并排
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

  // 术语表
  glossary: GlossaryEntry[];

  // 历史
  historyEnabled: boolean;
  historyMaxSize: number;

  // Butler 后端
  butlerBackendUrl: string;

  // 降级链
  fallbackChain: string[];  // provider id 列表，按优先级排列

  // 悬停翻译触发键（按住才显示整段译文，松开即消失）
  hoverTriggerKey: string;

  // AI 上下文翻译（页面摘要 + 术语一致性）
  ctxEnabled: boolean;

  // AI 专家 / 行业身份预设
  presets: PresetTemplate[];
  activePresetId: string;
  sitePresetBindings: SitePresetBinding[];

  // 输入框翻译
  inputTripleSpace: boolean;                 // 三连空格触发翻译
  inputDirection: 'auto' | 'zh-to-foreign' | 'foreign-to-zh';  // 双向切换

  // 用户自定义站点规则
  customSiteRules: SiteRule[];
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
  | { type: 'TRANSLATE'; texts: string[]; from?: LangCode; to: LangCode; providerId?: string; context?: { url: string; text: string } }
  | { type: 'TRANSLATE_SELECTION'; text: string }
  | { type: 'TRANSLATE_IMAGE'; base64: string }
  | { type: 'CAPTURE_VISIBLE_TAB' }
  | { type: 'GET_CONFIG' }
  | { type: 'SET_CONFIG'; config: Partial<TranslateConfig> }
  | { type: 'GET_PROVIDERS' }
  | { type: 'ADD_PROVIDER'; provider: ProviderConfig }
  | { type: 'UPDATE_PROVIDER'; id: string; patch: Partial<ProviderConfig> }
  | { type: 'DELETE_PROVIDER'; id: string }
  | { type: 'TEST_PROVIDER'; provider: ProviderConfig }
  | { type: 'GET_GLOSSARY' }
  | { type: 'ADD_GLOSSARY'; source: string; target: string }
  | { type: 'REMOVE_GLOSSARY'; source: string }
  | { type: 'GET_HISTORY'; limit?: number }
  | { type: 'CLEAR_HISTORY' }
  | { type: 'GET_PAGE_CONTEXT'; url: string; text: string }
  | { type: 'EXPORT_PDF'; pdfBase64: string; filename: string; to: LangCode }
  | { type: 'SYNC_GLOSSARY_PUSH' }
  | { type: 'SYNC_GLOSSARY_PULL' };

export type MsgResponse =
  | { type: 'TRANSLATE_RESULT'; results: TranslationResult[] }
  | { type: 'TRANSLATE_ERROR'; error: string; fallbackProvider?: string }
  | { type: 'CONFIG'; config: TranslateConfig }
  | { type: 'PROVIDERS'; providers: ProviderConfig[] }
  | { type: 'TEST_RESULT'; success: boolean; message: string }
  | { type: 'IMAGE_TRANSLATE_RESULT'; original: string; translated: string }
  | { type: 'CAPTURE_RESULT'; dataUrl: string }
  | { type: 'GLOSSARY'; entries: GlossaryEntry[] }
  | { type: 'HISTORY'; entries: HistoryEntry[] }
  | { type: 'PAGE_CONTEXT'; context: PageContext | null }
  | { type: 'EXPORT_RESULT'; success: boolean; message: string; dataUrl?: string; filename?: string }
  | { type: 'ACTION_RESULT'; success: boolean; message: string }
  | { type: 'OK' };

// ---------- 站点规则 ----------
export interface SiteRule {
  domain: string | RegExp;
  selectors?: string[];      // 要翻译的选择器
  exclude?: string[];        // 排除的选择器
  insertPosition?: 'afterend' | 'beforeend' | 'replace';
}
