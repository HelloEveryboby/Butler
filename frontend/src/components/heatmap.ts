/**
 * Butler Substrate Heatmap Background Canvas
 */

interface Particle {
  x: number;
  y: number;
  size: number;
  vx: number;
  vy: number;
}

class SubstrateHeatmap {
  public canvas: HTMLCanvasElement | null;
  public ctx: CanvasRenderingContext2D | null = null;
  public width: number = 0;
  public height: number = 0;
  public particles: Particle[] = [];
  public animating: boolean = true;

  constructor() {
    this.canvas = document.getElementById('substrate-heatmap') as HTMLCanvasElement;
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.onResize();

    this.initParticles();
    this.animate();

    window.addEventListener('resize', () => this.onResize());
  }

  public onResize(): void {
    if (!this.canvas) return;
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    this.canvas.width = this.width;
    this.canvas.height = this.height;
  }

  public initParticles(): void {
    const count = 50;
    this.particles = [];
    for (let i = 0; i < count; i++) {
      this.particles.push({
        x: Math.random() * this.width,
        y: Math.random() * this.height,
        size: Math.random() * 300 + 100,
        vx: Math.random() * 2 - 1,
        vy: Math.random() * 2 - 1,
      });
    }
  }

  public animate(): void {
    if (!this.ctx || !this.animating) return;
    this.ctx.clearRect(0, 0, this.width, this.height);

    const cpu = window.stateMatrix?.get('metrics.cpu') || 0;
    const mem = window.stateMatrix?.get('metrics.memory') || 0;

    const cpuValue = cpu / 100;
    const memValue = mem / 100;

    const speedFactor = 0.5 + cpuValue * 5;
    const densityFactor = 1 + memValue * 3;

    this.particles.forEach((p) => {
      p.x += p.vx * speedFactor;
      p.y += p.vy * speedFactor;

      if (p.x < -p.size) p.x = this.width + p.size;
      if (p.x > this.width + p.size) p.x = -p.size;
      if (p.y < -p.size) p.y = this.height + p.size;
      if (p.y > this.height + p.size) p.y = -p.size;

      const r = Math.floor(0 + cpuValue * 255);
      const g = Math.floor(100 + cpuValue * 50);
      const b = Math.floor(255 - cpuValue * 200);

      const gradient = this.ctx!.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size);
      gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${0.1 * densityFactor})`);
      gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);

      this.ctx!.fillStyle = gradient;
      this.ctx!.beginPath();
      this.ctx!.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      this.ctx!.fill();
    });

    requestAnimationFrame(() => this.animate());
  }

  public toggleAnimation(): void {
    this.animating = !this.animating;
    if (this.animating) {
      this.animate();
    }
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    const instance = new SubstrateHeatmap();
    (window as any).heatmap = instance;
    window.subtleHeatmap = instance;
    (window as any).SubstrateHeatmap = SubstrateHeatmap;
  });
}
