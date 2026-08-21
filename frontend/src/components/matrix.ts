/**
 * Butler Matrix Controller for 2x2 Spatial Navigation
 */

class MatrixController {
  public container: HTMLElement | null;
  public matrix: HTMLElement | null;
  public physicsX: any;
  public physicsY: any;

  constructor() {
    this.container = document.querySelector('.main-content');
    this.matrix = document.getElementById('workspace-matrix');

    const PhysicsClass = window.SpringPhysics;
    this.physicsX = new PhysicsClass(120, 20);
    this.physicsY = new PhysicsClass(120, 20);

    this.init();
  }

  public init(): void {
    // Sync Physics with StateMatrix
    this.physicsX.onUpdate((x: number) => {
      window.stateMatrix?.update('matrix.x', x);
    });
    this.physicsY.onUpdate((y: number) => {
      window.stateMatrix?.update('matrix.y', y);
    });

    // Global Render Loop for Matrix (Centralized)
    const render = () => {
      if (this.matrix && window.stateMatrix) {
        const x = window.stateMatrix.get('matrix.x') || 0;
        const y = window.stateMatrix.get('matrix.y') || 0;
        if (document.body.classList.contains('interface-mobile') && window.innerWidth > 768) {
          this.matrix.style.transform = `translate(${-x * 100}%, ${-y * 100}%)`;
        } else {
          this.matrix.style.transform = `translate(${-x * 100}vw, ${-y * 100}vh)`;
        }
      }
      requestAnimationFrame(render);
    };
    requestAnimationFrame(render);

    // Subscribe to Target changes to update Dock
    window.stateMatrix?.subscribe((state: any) => {
      this.updateDock(state.matrix.targetX, state.matrix.targetY);
    });

    window.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.ctrlKey) {
        const tx = window.stateMatrix?.get('matrix.targetX') || 0;
        const ty = window.stateMatrix?.get('matrix.targetY') || 0;
        switch (e.key) {
          case 'ArrowUp':
            this.moveTo(tx, ty - 1);
            break;
          case 'ArrowDown':
            this.moveTo(tx, ty + 1);
            break;
          case 'ArrowLeft':
            this.moveTo(tx - 1, ty);
            break;
          case 'ArrowRight':
            this.moveTo(tx + 1, ty);
            break;
        }
      }
    });

    let touchStartX = 0;
    let touchStartY = 0;
    if (this.container) {
      this.container.addEventListener(
        'touchstart',
        (e: TouchEvent) => {
          touchStartX = e.touches[0].clientX;
          touchStartY = e.touches[0].clientY;
        },
        { passive: true }
      );

      this.container.addEventListener(
        'touchend',
        (e: TouchEvent) => {
          const dx = e.changedTouches[0].clientX - touchStartX;
          const dy = e.changedTouches[0].clientY - touchStartY;
          if (Math.abs(dx) > 100 || Math.abs(dy) > 100) {
            const tx = window.stateMatrix?.get('matrix.targetX') || 0;
            const ty = window.stateMatrix?.get('matrix.targetY') || 0;
            if (Math.abs(dx) > Math.abs(dy)) {
              this.moveTo(tx - Math.sign(dx), ty);
            } else {
              this.moveTo(tx, ty - Math.sign(dy));
            }
          }
        },
        { passive: true }
      );
    }
  }

  public moveTo(nx: number, ny: number): void {
    if (nx < 0 || nx > 1 || ny < 0 || ny > 1) return;

    window.stateMatrix?.update('matrix.targetX', nx);
    window.stateMatrix?.update('matrix.targetY', ny);
    window.stateMatrix?.update('matrix.isMoving', true);

    this.physicsX.setTarget(nx);
    this.physicsY.setTarget(ny);

    // Auto-reset moving state when close
    setTimeout(() => {
      if (Math.abs(this.physicsX.x - nx) < 0.01 && Math.abs(this.physicsY.x - ny) < 0.01) {
        window.stateMatrix?.update('matrix.isMoving', false);
      }
    }, 1000);
  }

  public updateDock(nx: number, ny: number): void {
    const dockItems = document.querySelectorAll('.dock-item');
    dockItems.forEach((item) => {
      const id = `dock-${nx}-${ny}`;
      if (item.id === id) {
        item.classList.add('active');
      } else if (item.id.startsWith('dock-')) {
        item.classList.remove('active');
      }
    });

    // Dynamic PM Matrix non-linear zoom and blur spatial transition
    const targetCellId = `cell-${nx}-${ny}`;
    document.querySelectorAll('.matrix-cell').forEach((cell) => {
      if (cell.id === targetCellId) {
        cell.classList.add('active-cell');
        cell.classList.remove('inactive-cell');
      } else {
        cell.classList.add('inactive-cell');
        cell.classList.remove('active-cell');
      }
    });
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    window.matrix = new MatrixController();
  });
}
