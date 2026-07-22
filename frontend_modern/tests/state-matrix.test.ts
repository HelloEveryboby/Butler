import { describe, it, expect, vi, beforeEach } from 'vitest';
import { StateMatrix } from '@/stores/state-matrix';

// 使用具名导出的类以便测试独立实例
// 实际 src/stores/state-matrix.ts 导出的是单例，这里测试类本身
describe('StateMatrix', () => {
  let state: InstanceType<typeof StateMatrix>;

  beforeEach(() => {
    // 每个测试用例创建新实例 (通过重置单例)
    state = new (StateMatrix as any)();
  });

  it('should return initial state', () => {
    const matrix = state.get('matrix');
    expect(matrix.x).toBe(0);
    expect(matrix.y).toBe(0);
    expect(matrix.targetX).toBe(0);
    expect(matrix.targetY).toBe(0);
    expect(matrix.isMoving).toBe(false);
  });

  it('should update matrix state', () => {
    state.update('matrix', { x: 0.5, y: 0.5 });
    const matrix = state.get('matrix');
    expect(matrix.x).toBe(0.5);
    expect(matrix.y).toBe(0.5);
    // 其他字段应保持不变
    expect(matrix.targetX).toBe(0);
    expect(matrix.isMoving).toBe(false);
  });

  it('should update metrics', () => {
    state.update('metrics', { cpu: 75, memory: 60 });
    const metrics = state.get('metrics');
    expect(metrics.cpu).toBe(75);
    expect(metrics.memory).toBe(60);
    expect(metrics.disk).toBe(0); // 未更新的字段保持初始值
  });

  it('should notify listeners on update', () => {
    const listener = vi.fn();
    const unsub = state.subscribe(listener);

    state.update('matrix', { x: 1 });
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(state.snapshot());

    unsub();
  });

  it('should support unsubscribe', () => {
    const listener = vi.fn();
    const unsub = state.subscribe(listener);
    unsub();

    state.update('metrics', { cpu: 99 });
    expect(listener).not.toHaveBeenCalled();
  });

  it('should handle multiple listeners', () => {
    const l1 = vi.fn();
    const l2 = vi.fn();
    state.subscribe(l1);
    state.subscribe(l2);

    state.update('drag', { isDragging: true });
    expect(l1).toHaveBeenCalledTimes(1);
    expect(l2).toHaveBeenCalledTimes(1);
  });

  it('should return snapshot', () => {
    state.update('matrix', { x: 0.3 });
    const snap = state.snapshot();
    expect(snap.matrix.x).toBe(0.3);
    // snapshot 应该是引用 (当前实现是直接返回 state)
    expect(snap).toBe(state.snapshot());
  });

  it('should reset to initial state', () => {
    state.update('matrix', { x: 0.9, y: 0.9 });
    state.update('metrics', { cpu: 100 });
    state.reset();

    expect(state.get('matrix').x).toBe(0);
    expect(state.get('metrics').cpu).toBe(0);
  });

  it('should isolate partial updates', () => {
    state.update('matrix', { x: 0.5 });
    state.update('matrix', { y: 0.7 });

    const matrix = state.get('matrix');
    expect(matrix.x).toBe(0.5);
    expect(matrix.y).toBe(0.7);
  });

  it('should handle listener errors gracefully', () => {
    const badListener = vi.fn(() => {
      throw new Error('listener crash');
    });
    const goodListener = vi.fn();

    state.subscribe(badListener);
    state.subscribe(goodListener);

    // 不应抛出
    expect(() => state.update('matrix', { x: 1 })).not.toThrow();
    // 两个 listener 都应被调用
    expect(badListener).toHaveBeenCalled();
    expect(goodListener).toHaveBeenCalled();
  });
});
