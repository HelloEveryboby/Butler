/* ============================================================
   Butler Translate — 本地 vendor 资源加载
   ------------------------------------------------------------
   所有第三方运行时依赖（pdf.js / JSZip / tesseract.js / OCR 语言包）
   全部随扩展打包在 dist/vendor/ 下，通过 chrome.runtime.getURL 引用。
   默认【不访问公网】，兑现"完全离线、隐私安全"的产品承诺。
   ============================================================ */

/** vendor 资源根目录（相对于扩展根） */
const VENDOR_ROOT = 'vendor';

/** 把 vendor 内的相对路径转成 chrome-extension:// 完整 URL */
export function vendorUrl(relPath: string): string {
  return chrome.runtime.getURL(`${VENDOR_ROOT}/${relPath.replace(/^\/+/, '')}`);
}

/**
 * 以 <script> 方式加载一个 vendor 脚本（用于不便打包的库，如 tesseract.js）。
 * @param relPath vendor 相对路径，例如 'tesseract.min.js'
 */
export function loadVendorScript(relPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const src = vendorUrl(relPath);
    // 已加载过则直接返回（同名脚本只注入一次）
    if (document.querySelector(`script[data-butler-vendor="${relPath}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = src;
    script.dataset.butlerVendor = relPath;
    script.onload = () => resolve();
    script.onerror = () =>
      reject(new Error(`[ButlerTranslate] 加载本地 vendor 脚本失败: ${src}`));
    (document.head || document.documentElement).appendChild(script);
  });
}

/**
 * 动态 import 一个打包依赖（pdfjs-dist / jszip），webpack 会自动拆成独立 chunk，
 * 只在真正用到时才加载，避免拖慢 content script 启动。
 */
export async function loadPdfJs(): Promise<any> {
  const mod = await import('pdfjs-dist');
  const pdfjsLib: any = (mod as any).default ?? mod;
  // worker 必须显式指定到本地，否则 pdf.js 会去 CDN 找
  if (pdfjsLib.GlobalWorkerOptions && !pdfjsLib.GlobalWorkerOptions.workerSrc) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = vendorUrl('pdf.worker.min.mjs');
  }
  return pdfjsLib;
}

export async function loadJsZip(): Promise<any> {
  const mod = await import('jszip');
  return (mod as any).default ?? mod;
}

/* ---------- OCR（tesseract.js）本地化配置 ---------- */

export interface OcrRuntimeOptions {
  /** worker 脚本路径 */
  workerPath: string;
  /** wasm core 目录 */
  corePath: string;
  /** 训练数据（*.traineddata.gz）目录 */
  langPath: string;
}

/**
 * tesseract.js 运行时的本地路径配置。
 * 语言包由 `npm run fetch:ocr-lang` 下载到 vendor/lang/（可选组件，见其 README）。
 */
export function ocrRuntimeOptions(): OcrRuntimeOptions {
  return {
    workerPath: vendorUrl('tesseract.worker.min.js'),
    corePath: vendorUrl('tesseract-core'),
    langPath: vendorUrl('lang'),
  };
}
