/**
 * Butler StateMatrix: Single Source of Truth for high-frequency UI state.
 * Stores metrics, coordinates, drag states, and wormhole thresholds.
 */

interface MatrixState {
  matrix: {
    x: number;
    y: number;
    targetX: number;
    targetY: number;
    isMoving: boolean;
  };
  metrics: {
    cpu: number;
    memory: number;
    disk: number;
    network: number;
  };
  drag: {
    isDragging: boolean;
    sourceQuadrant: string | null;
    targetQuadrant: string | null;
    currentX: number;
    currentY: number;
    draggedId: string | null;
  };
  wormhole: {
    activeGate: string | null;
    pullStrength: number;
  };
  editor: {
    active: boolean;
    filePath: string | null;
  };
  timemachine: {
    active: boolean;
  };
}

type StateListener = (state: MatrixState) => void;

class StateMatrix {
  public state: MatrixState = {
    matrix: {
      x: 0,
      y: 0,
      targetX: 0,
      targetY: 0,
      isMoving: false,
    },
    metrics: {
      cpu: 0,
      memory: 0,
      disk: 0,
      network: 0,
    },
    drag: {
      isDragging: false,
      sourceQuadrant: null,
      targetQuadrant: null,
      currentX: 0,
      currentY: 0,
      draggedId: null,
    },
    wormhole: {
      activeGate: null,
      pullStrength: 0,
    },
    editor: {
      active: false,
      filePath: null,
    },
    timemachine: {
      active: false,
    },
  };

  private listeners: Set<StateListener> = new Set();

  public update(path: string, value: any): void {
    const parts = path.split('.');
    let current: any = this.state;
    for (let i = 0; i < parts.length - 1; i++) {
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = value;
    this.notify();
  }

  public get(path: string): any {
    const parts = path.split('.');
    let current: any = this.state;
    for (const part of parts) {
      if (current[part] === undefined) return undefined;
      current = current[part];
    }
    return current;
  }

  public updateFromBackend(data: any): void {
    if (data && data.metrics) {
      this.state.metrics = { ...this.state.metrics, ...data.metrics };
    }
    this.notify();
  }

  public subscribe(callback: StateListener): () => void {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  public notify(): void {
    this.listeners.forEach((callback) => callback(this.state));
  }
}

const stateMatrixInstance = new StateMatrix();

if (typeof window !== 'undefined') {
  (window as any).stateMatrix = stateMatrixInstance;
  (window as any).StateMatrix = stateMatrixInstance;
}
