/* ============================================================
   漫画气泡检测 — 白色/浅色区域连通域分析（纯函数，无 DOM 依赖）
   ------------------------------------------------------------
   输入：二值掩码（1 = 浅色候选像素），输出：气泡外接矩形。
   4 连通 BFS + 面积/填充率过滤，目标日漫气泡。
   ============================================================ */

export interface BubbleBox {
  x: number;
  y: number;
  w: number;
  h: number;
  /** 连通域像素数 */
  area: number;
}

export interface BubbleDetectOptions {
  /** 最小像素面积（过小的噪声丢弃） */
  minArea?: number;
  /** 最小宽度/高度 */
  minSize?: number;
  /** 填充率下限（area / (w*h)，气泡内部是实心浅色） */
  minFillRatio?: number;
  /** 最多返回气泡数（按面积降序） */
  maxBubbles?: number;
}

/**
 * 检测气泡（连通域）。
 * @param mask  二值掩码，长度 = width * height，1 = 浅色像素
 */
export function detectBubbles(
  mask: Uint8Array,
  width: number,
  height: number,
  opts: BubbleDetectOptions = {}
): BubbleBox[] {
  const minArea = opts.minArea ?? 300;
  const minSize = opts.minSize ?? 14;
  const minFillRatio = opts.minFillRatio ?? 0.38;
  const maxBubbles = opts.maxBubbles ?? 40;

  const visited = new Uint8Array(width * height);
  const boxes: BubbleBox[] = [];
  const stack: number[] = [];

  for (let start = 0; start < mask.length; start++) {
    if (mask[start] !== 1 || visited[start]) continue;

    // BFS/DFS 收集连通域
    stack.length = 0;
    stack.push(start);
    visited[start] = 1;

    let minX = width, minY = height, maxX = 0, maxY = 0, area = 0;

    while (stack.length > 0) {
      const idx = stack.pop()!;
      const x = idx % width;
      const y = (idx / width) | 0;
      area++;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;

      // 4 邻域
      if (x > 0) {
        const n = idx - 1;
        if (mask[n] === 1 && !visited[n]) { visited[n] = 1; stack.push(n); }
      }
      if (x < width - 1) {
        const n = idx + 1;
        if (mask[n] === 1 && !visited[n]) { visited[n] = 1; stack.push(n); }
      }
      if (y > 0) {
        const n = idx - width;
        if (mask[n] === 1 && !visited[n]) { visited[n] = 1; stack.push(n); }
      }
      if (y < height - 1) {
        const n = idx + width;
        if (mask[n] === 1 && !visited[n]) { visited[n] = 1; stack.push(n); }
      }
    }

    const w = maxX - minX + 1;
    const h = maxY - minY + 1;
    if (area < minArea) continue;
    if (w < minSize || h < minSize) continue;
    const fillRatio = area / (w * h);
    if (fillRatio < minFillRatio) continue;

    boxes.push({ x: minX, y: minY, w, h, area });
  }

  // 大气泡优先，截断
  boxes.sort((a, b) => b.area - a.area);
  return boxes.slice(0, maxBubbles);
}

/**
 * 构建浅色掩码（纯函数）：亮度高且低饱和的像素视为气泡内部候选。
 * @param rgba canvas ImageData 的 rgba 字节数组
 */
export function buildLightMask(
  rgba: Uint8ClampedArray | Uint8Array,
  width: number,
  height: number,
  luminanceThreshold = 210,
  saturationThreshold = 32
): Uint8Array {
  const mask = new Uint8Array(width * height);
  for (let i = 0, p = 0; i < mask.length; i++, p += 4) {
    const r = rgba[p];
    const g = rgba[p + 1];
    const b = rgba[p + 2];
    const lum = 0.299 * r + 0.587 * g + 0.114 * b;
    const sat = Math.max(r, g, b) - Math.min(r, g, b);
    mask[i] = lum >= luminanceThreshold && sat <= saturationThreshold ? 1 : 0;
  }
  return mask;
}
