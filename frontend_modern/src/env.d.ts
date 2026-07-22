/**
 * Butler 前端全局类型声明
 */

/** Vite 环境变量扩展 */
interface ImportMetaEnv {
  /** 开发模式 */
  readonly DEV: boolean;
  /** 生产模式 */
  readonly PROD: boolean;
  /** 基础 URL */
  readonly BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** CSS Modules 支持 */
declare module '*.module.css' {
  const classes: Record<string, string>;
  export default classes;
}

/** 静态资源 */
declare module '*.svg' {
  const src: string;
  export default src;
}

declare module '*.png' {
  const src: string;
  export default src;
}

declare module '*.jpg' {
  const src: string;
  export default src;
}

declare module '*.gif' {
  const src: string;
  export default src;
}

declare module '*.webp' {
  const src: string;
  export default src;
}

declare module '*.woff2' {
  const src: string;
  export default src;
}

declare module '*.woff' {
  const src: string;
  export default src;
}

/**
 * pywebview 全局对象
 * pywebview 注入到 window 上的 API
 */
interface PywebviewApi {
  handle_command(command: string): Promise<void>;
  submit_flash_command(command: string): void;
  hide_flash(): void;
  call_skill(skillName: string, method: string, params?: unknown): Promise<unknown>;
  pause_output(): void;
  open_office(filePath: string): void;
  terminal_input(data: string): void;
}

interface PywebviewWindow {
  api: PywebviewApi;
}

/**
 * pywebview evaluate_js 回调函数
 * Python 后端通过 evaluate_js 调用这些全局函数
 */
interface ButlerGlobalCallbacks {
  onAIStreamStart?: () => void;
  onAIStreamChunk?: (chunk: string) => void;
  onAIStreamEnd?: () => void;
  onProgressUpdate?: (value: number) => void;
  onProgressSync?: (data: unknown) => void;
  onNotificationPush?: (event: unknown) => void;
  onNotificationClose?: (data: unknown) => void;
  onTerminalOutput?: (output: unknown) => void;
  onFocusStart?: (message: string) => void;
  onFocusStop?: () => void;
  showToast?: (title: string, message: string, type?: string) => void;
  openEditor?: (content: string, filename: string) => void;
  triggerQuickAction?: (command: string, emoji: string) => void;
  toggleInterfaceMode?: () => void;
  startOnboardingTour?: () => void;
  nextOnboardingStep?: () => void;
  skipOnboarding?: () => void;
  matrix?: any;
}

declare interface Window extends ButlerGlobalCallbacks {
  pywebview?: PywebviewWindow;
  stateMatrix?: any;
  modernBridge?: any;
}
