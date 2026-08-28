/* ============================================================
   Butler Translate — 超时 + 二分重试
   ============================================================ */

/** 带超时的 Promise */
export function withTimeout<T>(promise: Promise<T>, ms: number, label = 'Operation'): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
    promise.then(
      (val) => { clearTimeout(timer); resolve(val); },
      (err) => { clearTimeout(timer); reject(err); }
    );
  });
}

/** 延迟 */
export function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms));
}

/**
 * 二分重试：当一大段文本翻译失败时，拆成两半分别翻译再合并
 */
export async function retryWithSplit<T>(
  texts: string[],
  translateFn: (batch: string[]) => Promise<T[]>,
  maxRetries = 2
): Promise<T[]> {
  try {
    return await translateFn(texts);
  } catch (err) {
    if (maxRetries <= 0 || texts.length <= 1) throw err;

    const mid = Math.floor(texts.length / 2);
    const left = texts.slice(0, mid);
    const right = texts.slice(mid);

    const [leftResult, rightResult] = await Promise.all([
      retryWithSplit(left, translateFn, maxRetries - 1),
      retryWithSplit(right, translateFn, maxRetries - 1),
    ]);

    return [...leftResult, ...rightResult];
  }
}
