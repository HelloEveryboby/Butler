/**
 * Butler Matrix Wormhole Spatial Drag Transport Manager
 */

class MatrixWormhole {
  public gates: NodeListOf<HTMLElement>;
  public isDragging: boolean = false;
  public draggedElement: HTMLElement | null = null;

  constructor() {
    this.gates = document.querySelectorAll('.wormhole-gate');
    this.init();
  }

  public init(): void {
    document.addEventListener('dragstart', (e) => this.onDragStart(e));
    document.addEventListener('drag', (e) => this.onDrag(e));
    document.addEventListener('dragend', (e) => this.onDragEnd(e));

    this.gates.forEach((gate) => {
      gate.addEventListener('dragover', (e) => {
        e.preventDefault();
        gate.classList.add('pulling');
      });
      gate.addEventListener('dragleave', () => {
        gate.classList.remove('pulling');
      });
      gate.addEventListener('drop', (e) => this.onDrop(e, gate));
    });
  }

  public onDragStart(e: DragEvent): void {
    const target = e.target as HTMLElement;
    if (target && (target.classList.contains('skill-card') || target.closest('.skill-card'))) {
      this.isDragging = true;
      this.draggedElement = target.closest('.skill-card');
      this.showGates();
    }
  }

  public onDrag(e: DragEvent): void {
    if (!this.isDragging) return;
  }

  public onDragEnd(e: DragEvent): void {
    this.isDragging = false;
    this.hideGates();
  }

  public showGates(): void {
    this.gates.forEach((gate) => gate.classList.add('active'));
  }

  public hideGates(): void {
    this.gates.forEach((gate) => gate.classList.remove('active', 'pulling'));
  }

  public async onDrop(e: DragEvent, gate: HTMLElement): Promise<void> {
    e.preventDefault();
    const targetQuadrant = gate.dataset.quadrant || '0,0';
    const [qx, qy] = targetQuadrant.split(',').map(Number);

    if (this.draggedElement) {
      this.draggedElement.classList.add('key-dissolve');

      setTimeout(() => {
        const skillId = this.draggedElement?.dataset.skillId || 'skill';
        this.transportSkill(skillId, qx, qy);

        if (this.draggedElement && this.draggedElement.parentNode) {
          this.draggedElement.parentNode.removeChild(this.draggedElement);
        }
        this.draggedElement = null;
      }, 800);
    }
  }

  public transportSkill(skillId: string, qx: number, qy: number): void {
    if (window.matrix) {
      window.matrix.moveTo(qx, qy);
    }

    if (qx === 0 && qy === 1 && window.dagEngine) {
      window.dagEngine.addNode(skillId, 'fa-cube', 100, 100);
    }

    console.log(`Skill ${skillId} transported to (${qx}, ${qy})`);
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    window.wormhole = new MatrixWormhole();
    (window as any).MatrixWormhole = MatrixWormhole;
  });
}
