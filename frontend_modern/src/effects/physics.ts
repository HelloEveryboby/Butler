/**
 * 弹簧物理引擎 (Spring Physics)
 *
 * 基于阻尼弹簧模型，用于 2x2 矩阵导航的丝滑过渡动画。
 * 替代 CSS transition，提供更自然的物理反馈。
 *
 * @example
 * ```ts
 * const spring = new SpringPhysics(120, 20);
 * spring.onUpdate((value) => {
 *   element.style.transform = `translateX(${value * 100}%)`;
 * });
 * spring.setTarget(1);
 * ```
 */

export class SpringPhysics {
  /** 当前位置 */
  x: number;

  /** 当前速度 */
  private velocity: number;

  /** 目标位置 */
  private target: number;

  /** 弹簧刚度 (越大越快) */
  private stiffness: number;

  /** 阻尼系数 (越大振荡越少) */
  private damping: number;

  /** 更新回调列表 */
  private callbacks: Array<(value: number) => void> = [];

  /** 动画帧 ID */
  private rafId: number | null = null;

  /** 精度阈值 (低于此值视为到达目标) */
  private readonly epsilon = 0.001;

  /** 是否正在运行 */
  private running = false;

  constructor(stiffness = 120, damping = 20, initialValue = 0) {
    this.x = initialValue;
    this.velocity = 0;
    this.target = initialValue;
    this.stiffness = stiffness;
    this.damping = damping;
  }

  /**
   * 设置目标位置，自动开始动画
   */
  setTarget(target: number): void {
    this.target = target;
    if (!this.running) {
      this.running = true;
      this.tick();
    }
  }

  /**
   * 立即跳到指定位置 (无动画)
   */
  jumpTo(value: number): void {
    this.x = value;
    this.velocity = 0;
    this.target = value;
    this.emit();
  }

  /**
   * 注册更新回调
   */
  onUpdate(callback: (value: number) => void): void {
    this.callbacks.push(callback);
  }

  /**
   * 停止动画
   */
  stop(): void {
    this.running = false;
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  /**
   * 是否已到达目标
   */
  get isSettled(): boolean {
    return (
      Math.abs(this.x - this.target) < this.epsilon &&
      Math.abs(this.velocity) < this.epsilon
    );
  }

  /**
   * 手动推进一帧 (用于测试或自定义渲染循环)
   * @param dt - 时间步长 (秒)
   */
  update(dt: number): void {
    // 弹簧力: F = -k * (x - target)
    const springForce = -this.stiffness * (this.x - this.target);
    // 阻尼力: F = -d * v
    const dampingForce = -this.damping * this.velocity;
    // 加速度
    const acceleration = springForce + dampingForce;

    // 半隐式欧拉积分 (比显式欧拉更稳定)
    this.velocity += acceleration * dt;
    this.x += this.velocity * dt;
  }

  private tick = (): void => {
    if (!this.running) return;

    // 固定时间步长 1/60 秒
    this.update(1 / 60);

    this.emit();

    if (this.isSettled) {
      // 吸附到目标
      this.x = this.target;
      this.velocity = 0;
      this.emit();
      this.running = false;
      return;
    }

    this.rafId = requestAnimationFrame(this.tick);
  };

  private emit(): void {
    for (const cb of this.callbacks) {
      cb(this.x);
    }
  }
}
