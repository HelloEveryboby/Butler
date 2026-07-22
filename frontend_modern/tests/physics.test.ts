import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SpringPhysics } from '@/effects/physics';

describe('SpringPhysics', () => {
  let spring: SpringPhysics;

  beforeEach(() => {
    spring = new SpringPhysics(120, 20, 0);
  });

  it('should initialize with default values', () => {
    expect(spring.x).toBe(0);
    expect(spring.isSettled).toBe(true); // at target (0)
  });

  it('should accept initial value', () => {
    const s = new SpringPhysics(120, 20, 0.5);
    expect(s.x).toBe(0.5);
  });

  it('should converge to target', () => {
    spring.setTarget(1);

    // Run 120 frames (~2 seconds at 60fps)
    for (let i = 0; i < 120; i++) {
      spring.update(1 / 60);
    }

    expect(spring.x).toBeCloseTo(1, 1);
  });

  it('should notify onUpdate callbacks', () => {
    const callback = vi.fn();
    spring.onUpdate(callback);

    spring.setTarget(1);
    spring.update(1 / 60);

    expect(callback).toHaveBeenCalled();
    expect(callback).toHaveBeenCalledWith(spring.x);
  });

  it('should jumpTo without animation', () => {
    spring.setTarget(1);
    spring.update(1 / 60); // start moving

    spring.jumpTo(0.5);
    expect(spring.x).toBe(0.5);
    expect(spring.isSettled).toBe(false); // target is still 1
  });

  it('should stop animation', () => {
    spring.setTarget(1);
    spring.update(1 / 60);
    spring.stop();

    const xBefore = spring.x;
    spring.update(1 / 60); // should not advance
    expect(spring.x).toBe(xBefore);
  });

  it('should handle zero stiffness (no movement)', () => {
    const s = new SpringPhysics(0, 20, 0);
    s.setTarget(1);
    s.update(1 / 60);
    expect(s.x).toBe(0); // no force = no movement
  });

  it('should oscillate with low damping', () => {
    // Low damping = more oscillation
    const s = new SpringPhysics(120, 2, 0);
    s.setTarget(1);

    const values: number[] = [];
    for (let i = 0; i < 60; i++) {
      s.update(1 / 60);
      values.push(s.x);
    }

    // Should overshoot past 1
    const maxVal = Math.max(...values);
    expect(maxVal).toBeGreaterThan(1);
  });

  it('should not overshoot with high damping', () => {
    // High damping = critically damped, no overshoot
    const s = new SpringPhysics(120, 50, 0);
    s.setTarget(1);

    const values: number[] = [];
    for (let i = 0; i < 120; i++) {
      s.update(1 / 60);
      values.push(s.x);
    }

    const maxVal = Math.max(...values);
    expect(maxVal).toBeLessThanOrEqual(1.01); // minimal overshoot
  });

  it('should report isSettled correctly', () => {
    const s = new SpringPhysics(120, 20, 0);
    s.setTarget(1);

    // Not settled initially (moving toward target)
    s.update(1 / 60);
    expect(s.isSettled).toBe(false);

    // Run enough frames to settle
    for (let i = 0; i < 200; i++) {
      s.update(1 / 60);
    }
    expect(s.isSettled).toBe(true);
  });
});
