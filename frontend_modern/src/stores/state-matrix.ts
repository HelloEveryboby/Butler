/**
 * Butler StateMatrix: 全局 UI 状态的单一来源
 *
 * 替代原来的 window.stateMatrix 全局变量。
 * 使用发布-订阅模式管理 2x2 矩阵的坐标、系统指标、拖拽状态等。
 *
 * @example
 * ```ts
 * import { stateMatrix } from '@/stores/state-matrix';
 *
 * // 读取状态
 * const { x, y } = stateMatrix.get('matrix');
 *
 * // 更新状态
 * stateMatrix.update('matrix', { x: 0.5, y: 0.5 });
 *
 * // 订阅变化
 * const unsubscribe = stateMatrix.subscribe((state) => {
 *   console.log('Matrix:', state.matrix);
 * });
 * ```
 */

export interface MatrixState {
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  isMoving: boolean;
}

export interface MetricsState {
  cpu: number;
  memory: number;
  disk: number;
  network: number;
}

export interface DragState {
  isDragging: boolean;
  sourceQuadrant: string | null;
  targetQuadrant: string | null;
  currentX: number;
  currentY: number;
  draggedId: string | null;
}

export interface WormholeState {
  activeGate: string | null;
  pullStrength: number;
}

export interface EditorState {
  active: boolean;
  filePath: string | null;
}

export interface TimeMachineState {
  active: boolean;
}

export interface StateShape {
  matrix: MatrixState;
  metrics: MetricsState;
  drag: DragState;
  wormhole: WormholeState;
  editor: EditorState;
  timemachine: TimeMachineState;
}

export type StateListener = (state: Readonly<StateShape>) => void;

const INITIAL_STATE: StateShape = {
  matrix: { x: 0, y: 0, targetX: 0, targetY: 0, isMoving: false },
  metrics: { cpu: 0, memory: 0, disk: 0, network: 0 },
  drag: {
    isDragging: false,
    sourceQuadrant: null,
    targetQuadrant: null,
    currentX: 0,
    currentY: 0,
    draggedId: null,
  },
  wormhole: { activeGate: null, pullStrength: 0 },
  editor: { active: false, filePath: null },
  timemachine: { active: false },
};

class StateMatrix {
  private state: StateShape;
  private listeners = new Set<StateListener>();

  constructor(initialState: StateShape = INITIAL_STATE) {
    this.state = structuredClone(initialState);
  }

  /**
   * 更新指定路径的状态
   * @param key - 状态顶级键
   * @param partial - 部分状态更新 (会浅合并)
   */
  update<K extends keyof StateShape>(key: K, partial: Partial<StateShape[K]>): void {
    this.state[key] = { ...this.state[key], ...partial };
    this.notify();
  }

  /**
   * 读取指定路径的状态 (返回副本)
   */
  get<K extends keyof StateShape>(key: K): Readonly<StateShape[K]> {
    return this.state[key];
  }

  /**
   * 获取完整状态快照 (只读)
   */
  snapshot(): Readonly<StateShape> {
    return this.state;
  }

  /**
   * 订阅状态变化
   * @returns 取消订阅函数
   */
  subscribe(listener: StateListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * 重置为初始状态
   */
  reset(): void {
    this.state = structuredClone(INITIAL_STATE);
    this.notify();
  }

  private notify(): void {
    for (const cb of this.listeners) {
      try {
        cb(this.state);
      } catch (err) {
        console.error('[StateMatrix] listener error:', err);
      }
    }
  }
}

/** 全局单例 */
export const stateMatrix = new StateMatrix();

// 向后兼容: 暴露到 window 上，供 pywebview evaluate_js 使用
if (typeof window !== 'undefined') {
  (window as any).stateMatrix = stateMatrix;
}
