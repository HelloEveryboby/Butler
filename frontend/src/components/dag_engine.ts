/**
 * Butler DAG Engine: SVG-based connection lines and draggable skill nodes.
 */

interface DAGNode {
  id: string;
  el: HTMLElement;
}

interface DAGConnection {
  from: string;
  to: string;
}

class DAGEngine {
  public canvas: HTMLElement | null;
  public svg: SVGElement | null;
  public nodes: DAGNode[] = [];
  public connections: DAGConnection[] = [];
  public isConnecting: boolean = false;
  public tempLine: { from: string; startX: number; startY: number } | null = null;
  public isRunning: boolean = false;

  constructor() {
    this.canvas = document.getElementById('workflow-canvas');
    this.svg = document.getElementById('dag-svg') as unknown as SVGElement;

    this.init();
  }

  public init(): void {
    if (!this.canvas) return;

    this.canvas.addEventListener('dragover', (e) => e.preventDefault());
    this.canvas.addEventListener('drop', (e) => this.onDrop(e));

    this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));

    const render = () => {
      this.updateConnections();
      requestAnimationFrame(render);
    };
    requestAnimationFrame(render);
  }

  public onDrop(e: DragEvent): void {
    e.preventDefault();
    if (!e.dataTransfer || !this.canvas) return;
    const dataStr = e.dataTransfer.getData('application/json');
    if (!dataStr) return;

    try {
      const data = JSON.parse(dataStr);
      if (data.type === 'skill') {
        const rect = this.canvas.getBoundingClientRect();
        this.addNode(data.name, data.icon, e.clientX - rect.left - 60, e.clientY - rect.top - 30);

        const placeholder = this.canvas.querySelector('.canvas-placeholder') as HTMLElement;
        if (placeholder) placeholder.style.display = 'none';
      }
    } catch (err) {
      console.error('[DAGEngine] Failed to parse dropped skill data:', err);
    }
  }

  public addNode(name: string, icon: string, x: number, y: number): void {
    if (!this.canvas) return;

    const node = document.createElement('div');
    node.className = 'dag-node glass-surface damping-transition';
    node.style.left = `${x}px`;
    node.style.top = `${y}px`;

    const nodeId = `node-${Date.now()}`;
    node.id = nodeId;
    node.dataset.skillId = name;

    node.innerHTML = `
      <div class="node-input-slot" data-node-id="${nodeId}"></div>
      <i class="fas ${icon}"></i>
      <span>${name}</span>
      <div class="node-output-slot" data-node-id="${nodeId}"></div>
    `;

    this.canvas.appendChild(node);
    this.makeDraggable(node);

    const outputSlot = node.querySelector('.node-output-slot');
    const inputSlot = node.querySelector('.node-input-slot');

    if (outputSlot) {
      outputSlot.addEventListener('mousedown', (e) => this.startConnection(e as MouseEvent, nodeId));
    }
    if (inputSlot) {
      inputSlot.addEventListener('mouseup', (e) => this.endConnection(e as MouseEvent, nodeId));
    }

    this.nodes.push({ id: nodeId, el: node });
  }

  public makeDraggable(el: HTMLElement): void {
    let isDragging = false;
    let startX = 0;
    let startY = 0;

    el.addEventListener('mousedown', (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains('node-output-slot') || target.classList.contains('node-input-slot')) return;
      isDragging = true;
      startX = e.clientX - el.offsetLeft;
      startY = e.clientY - el.offsetTop;
      el.style.transition = 'none';
      el.classList.add('dragging');
    });

    document.addEventListener('mousemove', (e: MouseEvent) => {
      if (!isDragging) return;
      el.style.left = `${e.clientX - startX}px`;
      el.style.top = `${e.clientY - startY}px`;
    });

    document.addEventListener('mouseup', () => {
      if (!isDragging) return;
      isDragging = false;
      el.style.transition = '';
      el.classList.remove('dragging');
    });
  }

  public startConnection(e: MouseEvent, nodeId: string): void {
    e.stopPropagation();
    if (!this.canvas) return;
    this.isConnecting = true;
    const target = e.target as HTMLElement;
    const rect = target.getBoundingClientRect();
    const canvasRect = this.canvas.getBoundingClientRect();

    this.tempLine = {
      from: nodeId,
      startX: rect.left + rect.width / 2 - canvasRect.left,
      startY: rect.top + rect.height / 2 - canvasRect.top,
    };
  }

  public endConnection(e: MouseEvent, nodeId: string): void {
    if (this.isConnecting && this.tempLine && this.tempLine.from !== nodeId) {
      this.connections.push({
        from: this.tempLine.from,
        to: nodeId,
      });
    }
    this.isConnecting = false;
    this.tempLine = null;
    if (this.svg) this.svg.innerHTML = '';
  }

  public onMouseMove(e: MouseEvent): void {
    if (this.isConnecting && this.tempLine && this.canvas) {
      const canvasRect = this.canvas.getBoundingClientRect();
      this.drawTempLine(
        this.tempLine.startX,
        this.tempLine.startY,
        e.clientX - canvasRect.left,
        e.clientY - canvasRect.top
      );
    }
  }

  public drawTempLine(x1: number, y1: number, x2: number, y2: number): void {
    if (!this.svg) return;
    this.svg.innerHTML = '';
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${x1} ${y1} C ${x1 + 50} ${y1}, ${x2 - 50} ${y2}, ${x2} ${y2}`;
    path.setAttribute('d', d);
    path.setAttribute('stroke', 'var(--accent-color)');
    path.setAttribute('stroke-width', '2');
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke-dasharray', '5,5');
    this.svg.appendChild(path);
  }

  public updateConnections(): void {
    if (!this.canvas || !this.svg) return;

    if (this.connections.length === 0 && !this.isConnecting) {
      this.svg.innerHTML = '';
      return;
    }

    let html = '';
    const canvasRect = this.canvas.getBoundingClientRect();

    this.connections.forEach((conn) => {
      const fromNode = document.getElementById(conn.from);
      const toNode = document.getElementById(conn.to);
      if (!fromNode || !toNode) return;

      const fromOutEl = fromNode.querySelector('.node-output-slot');
      const toInEl = toNode.querySelector('.node-input-slot');
      if (!fromOutEl || !toInEl) return;

      const fromOut = fromOutEl.getBoundingClientRect();
      const toIn = toInEl.getBoundingClientRect();

      const x1 = fromOut.left + fromOut.width / 2 - canvasRect.left;
      const y1 = fromOut.top + fromOut.height / 2 - canvasRect.top;
      const x2 = toIn.left + toIn.width / 2 - canvasRect.left;
      const y2 = toIn.top + toIn.height / 2 - canvasRect.top;

      const runningClass = this.isRunning ? 'running-flow' : '';
      html += `<path class="dag-svg-path ${runningClass}" d="M ${x1} ${y1} C ${x1 + 50} ${y1}, ${x2 - 50} ${y2}, ${x2} ${y2}"
                     stroke="var(--accent-color)" stroke-width="2.5" fill="none" />`;
    });

    if (!this.isConnecting || !this.tempLine) {
      this.svg.innerHTML = html;
    }
  }

  public runPipeline(): void {
    if (this.nodes.length === 0) {
      window.showToast?.('任务流水线', '画布中没有检测到可执行的技能节点！请从左侧拖入技能卡片。', 'error');
      return;
    }

    this.isRunning = true;
    window.showToast?.('任务流水线', '流水线已启动。正在进行拓扑排序并分配执行节点...', 'success');

    this.nodes.forEach((node) => {
      this.setNodeStatus(node.el, 'loading', '执行中...');
    });

    this.nodes.forEach((node, idx) => {
      setTimeout(() => {
        if (!this.isRunning) return;
        this.setNodeStatus(node.el, 'success', '✔ 成功');
        const skillName = node.el.dataset.skillId || '技能';
        window.showToast?.('执行成功', `步骤 [${skillName}] 已成功完成。`, 'success');

        if (idx === this.nodes.length - 1) {
          this.isRunning = false;
          window.showToast?.('流水线执行完成', '所有 DAG 节点已顺利执行完毕，状态已保存。', 'success');
        }
      }, (idx + 1) * 1500);
    });
  }

  public pausePipeline(): void {
    this.isRunning = false;
    this.nodes.forEach((node) => {
      const badge = node.el.querySelector('.dag-node-status-badge');
      if (badge) badge.remove();
    });
    window.showToast?.('任务流水线', '流水线已成功暂停。', 'warning');
  }

  public clearCanvas(): void {
    if (!this.canvas || !this.svg) return;
    this.isRunning = false;
    this.connections = [];
    this.nodes = [];

    const nodesToClear = this.canvas.querySelectorAll('.dag-node');
    nodesToClear.forEach((node) => node.remove());

    this.svg.innerHTML = '';

    const placeholder = this.canvas.querySelector('.canvas-placeholder') as HTMLElement;
    if (placeholder) placeholder.style.display = 'flex';

    window.showToast?.('任务流水线', '画布已清空并复位。', 'success');
  }

  public setNodeStatus(nodeEl: HTMLElement, status: string, text: string): void {
    let badge = nodeEl.querySelector('.dag-node-status-badge') as HTMLElement;
    if (!badge) {
      badge = document.createElement('div');
      nodeEl.appendChild(badge);
    }
    badge.className = `dag-node-status-badge ${status}`;
    badge.innerText = text;
  }
}

window.runDagPipeline = () => {
  if (window.dagEngine) window.dagEngine.runPipeline();
};

window.pauseDagPipeline = () => {
  if (window.dagEngine) window.dagEngine.pausePipeline();
};

window.clearDagCanvas = () => {
  if (window.dagEngine) window.dagEngine.clearCanvas();
};

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    (window as any).dagEngine = new DAGEngine();
    (window as any).DAGEngine = DAGEngine;
  });
}
