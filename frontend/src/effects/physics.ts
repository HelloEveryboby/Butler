/**
 * Lightweight Spring Physics Engine for Butler UI.
 * Zero-dependency implementation of Hooke's Law with Damping.
 * Optimized for StateMatrix synchronization.
 */
class SpringPhysics {
  public k: number;
  public c: number;
  public m: number;

  public x: number = 0;
  public v: number = 0;
  public target: number = 0;

  private listeners: Array<(x: number) => void> = [];
  private animating: boolean = false;
  private lastTime: number = 0;

  constructor(stiffness: number = 170, damping: number = 26, mass: number = 1) {
    this.k = stiffness;
    this.c = damping;
    this.m = mass;
  }

  public setTarget(v: number): void {
    this.target = v;
    if (!this.animating) {
      this.start();
    }
  }

  public setCurrent(v: number): void {
    this.x = v;
  }

  public start(): void {
    this.animating = true;
    this.lastTime = performance.now();
    this.updateFrame();
  }

  private updateFrame(): void {
    if (!this.animating) return;

    const now = performance.now();
    const dt = Math.min((now - this.lastTime) / 1000, 0.1);
    this.lastTime = now;

    const fSpring = -this.k * (this.x - this.target);
    const fDamper = -this.c * this.v;
    const a = (fSpring + fDamper) / this.m;

    this.v += a * dt;
    this.x += this.v * dt;

    this.listeners.forEach((fn) => fn(this.x));

    if (Math.abs(this.v) < 0.001 && Math.abs(this.x - this.target) < 0.001) {
      this.x = this.target;
      this.v = 0;
      this.animating = false;
      return;
    }

    requestAnimationFrame(() => this.updateFrame());
  }

  public onUpdate(fn: (x: number) => void): void {
    this.listeners.push(fn);
  }
}

if (typeof window !== 'undefined') {
  (window as any).SpringPhysics = SpringPhysics;
}
