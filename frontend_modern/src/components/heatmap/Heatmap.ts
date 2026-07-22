/**
 * Heatmap: 热力图可视化
 *
 * 基于 Canvas 的热力图渲染，用于系统状态可视化。
 */

export class Heatmap {
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;

  constructor(canvasId = 'heatmap-canvas') {
    this.canvas = document.getElementById(canvasId) as HTMLCanvasElement;
    if (this.canvas) {
      this.ctx = this.canvas.getContext('2d');
    }
  }

  /**
   * 绘制热力图
   * @param data - 二维数值数组 (0-1 范围)
   */
  draw(data: number[][]): void {
    const ctx = this.ctx;
    const canvas = this.canvas;
    if (!ctx || !canvas || data.length === 0) return;

    const rows = data.length;
    const cols = data[0].length;
    const cellW = canvas.width / cols;
    const cellH = canvas.height / rows;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const value = Math.max(0, Math.min(1, data[y][x]));
        ctx.fillStyle = this.valueToColor(value);
        ctx.fillRect(x * cellW, y * cellH, cellW, cellH);
      }
    }
  }

  private valueToColor(value: number): string {
    // 绿(0) → 黄(0.5) → 红(1)
    const r = Math.round(value < 0.5 ? value * 2 * 255 : 255);
    const g = Math.round(value < 0.5 ? 255 : (1 - (value - 0.5) * 2) * 255);
    const b = 0;
    return `rgb(${r},${g},${b})`;
  }
}
