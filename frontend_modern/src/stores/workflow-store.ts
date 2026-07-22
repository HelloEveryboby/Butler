/**
 * 工作流状态管理
 *
 * 管理 DAG 工作流的列表、执行状态。
 */

export interface WorkflowStep {
  intent: string;
  status?: 'pending' | 'running' | 'completed' | 'failed';
}

export interface Workflow {
  id: string;
  name: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  currentStep: number;
  steps: WorkflowStep[];
}

type Listener = (workflows: Map<string, Workflow>) => void;

class WorkflowStore {
  private workflows = new Map<string, Workflow>();
  private listeners = new Set<Listener>();

  get(id: string): Workflow | undefined {
    return this.workflows.get(id);
  }

  getAll(): ReadonlyMap<string, Workflow> {
    return this.workflows;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /** 从后端数据批量更新 */
  sync(data: Record<string, any>): void {
    this.workflows.clear();
    for (const [id, wf] of Object.entries(data)) {
      this.workflows.set(id, {
        id,
        name: wf.name || id,
        status: wf.status || 'idle',
        currentStep: wf.current_step || 0,
        steps: (wf.steps || []).map((s: any) => ({
          intent: s.intent || '',
          status: s.status || 'pending',
        })),
      });
    }
    this.notify();
  }

  /** 更新单个工作流状态 */
  updateStatus(id: string, status: Workflow['status']): void {
    const wf = this.workflows.get(id);
    if (wf) {
      this.workflows.set(id, { ...wf, status });
      this.notify();
    }
  }

  private notify(): void {
    for (const cb of this.listeners) {
      try {
        cb(this.workflows);
      } catch (err) {
        console.error('[WorkflowStore] listener error:', err);
      }
    }
  }
}

export const workflowStore = new WorkflowStore();
