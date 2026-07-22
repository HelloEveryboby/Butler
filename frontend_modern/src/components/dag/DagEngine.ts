/**
 * DagEngine: DAG 可视化任务流水线 (性能优化版)
 *
 * 优化:
 * - rAF 循环只在有节点时运行
 * - 提供 destroy() 停止循环
 * - canvas 不存在时跳过初始化
 */

import { stateMatrix } from '@/stores/state-matrix';
import { toast } from '@/utils/toast';

export interface DagNode {
  id: string;
  label: string;
  skillName: string;
  x: number;
  y: number;
  status: 'idle' | 'running' | 'completed' | 'failed';
}

export interface DagEdge {
  id: string;
  from: string;
  to: string;
}

export class DagEngine {
  private nodes: Map<string, DagNode> = new Map();
  private edges: DagEdge[] = [];
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private selectedNode: string | null = null;
  private isDragging = false;
  private rafId: number | null = null;
  private running = false;

  constructor() {
    this.init();
  }

  private init(): void {
    this.canvas = document.getElementById('dag-canvas') as HTMLCanvasElement;
    if (!this.canvas) return; // canvas 不存在时跳过

    this.ctx = this.canvas.getContext('2d');
    this.resizeCanvas();
    this.bindEvents();
    this.startRenderLoop();

    stateMatrix.subscribe((state) => {
      if (!state.drag.isDragging && state.drag.draggedId && state.drag.targetQuadrant === '0,1') {
        this.addNodeFromSkill(state.drag.draggedId, state.drag.currentX, state.drag.currentY);
      }
    });
  }

  private resizeCanvas(): void {
    if (!this.canvas) return;
    const rect = this.canvas.parentElement?.getBoundingClientRect();
    if (rect) {
      this.canvas.width = rect.width;
      this.canvas.height = rect.height;
    }
  }

  private bindEvents(): void {
    if (!this.canvas) return;

    this.canvas.addEventListener('mousedown', (e) => {
      const rect = this.canvas!.getBoundingClientRect();
      this.selectedNode = this.hitTest(e.clientX - rect.left, e.clientY - rect.top);
      this.isDragging = !!this.selectedNode;
    });

    this.canvas.addEventListener('mousemove', (e) => {
      if (!this.isDragging || !this.selectedNode) return;
      const rect = this.canvas!.getBoundingClientRect();
      const node = this.nodes.get(this.selectedNode);
      if (node) {
        node.x = e.clientX - rect.left;
        node.y = e.clientY - rect.top;
      }
    });

    this.canvas.addEventListener('mouseup', () => {
      this.isDragging = false;
      this.selectedNode = null;
    });

    window.addEventListener('resize', () => this.resizeCanvas());
  }

  addNodeFromSkill(skillId: string, x: number, y: number): void {
    const id = `node-${Date.now()}`;
    this.nodes.set(id, { id, label: skillId, skillName: skillId, x, y, status: 'idle' });
    toast.info('DAG', `已添加节点: ${skillId}`);
  }

  addEdge(fromId: string, toId: string): void {
    if (!this.nodes.has(fromId) || !this.nodes.has(toId)) return;
    this.edges.push({ id: `edge-${fromId}-${toId}`, from: fromId, to: toId });
  }

  private hitTest(x: number, y: number): string | null {
    for (const [id, node] of this.nodes) {
      const dx = x - node.x;
      const dy = y - node.y;
      if (Math.sqrt(dx * dx + dy * dy) < 40) return id;
    }
    return null;
  }

  // === 按需渲染循环 ===

  private startRenderLoop(): void {
    if (this.running) return;
    this.running = true;
    this.tick();
  }

  private tick = (): void => {
    if (!this.running) return;
    this.draw();
    this.rafId = requestAnimationFrame(this.tick);
  };

  private draw(): void {
    const ctx = this.ctx;
    const canvas = this.canvas;
    if (!ctx || !canvas) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 连线
    for (const edge of this.edges) {
      const from = this.nodes.get(edge.from);
      const to = this.nodes.get(edge.to);
      if (!from || !to) continue;

      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.strokeStyle = 'rgba(0, 122, 255, 0.6)';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // 节点
    const colors: Record<string, string> = {
      idle: 'rgba(255, 255, 255, 0.1)',
      running: 'rgba(33, 150, 243, 0.3)',
      completed: 'rgba(52, 199, 89, 0.3)',
      failed: 'rgba(255, 59, 48, 0.3)',
    };

    for (const [, node] of this.nodes) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, 30, 0, Math.PI * 2);
      ctx.fillStyle = colors[node.status] || colors.idle;
      ctx.fill();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.fillStyle = '#ffffff';
      ctx.font = '11px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.label, node.x, node.y);
    }
  }

  getData(): { nodes: DagNode[]; edges: DagEdge[] } {
    return {
      nodes: Array.from(this.nodes.values()),
      edges: [...this.edges],
    };
  }

  clear(): void {
    this.nodes.clear();
    this.edges = [];
  }

  destroy(): void {
    this.running = false;
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.nodes.clear();
    this.edges = [];
  }
}
