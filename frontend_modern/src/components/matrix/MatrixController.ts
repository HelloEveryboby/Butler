/**
 * MatrixController: 2x2 矩阵导航控制器 (性能优化版)
 *
 * 优化:
 * - rAF 循环只在动画期间运行，非永续循环
 * - 移动端跳过 transform 更新 (用 display:none/block 切换)
 * - 用 will-change:transform 仅在动画期间
 * - 减少不必要的状态更新
 */

import { stateMatrix } from '@/stores/state-matrix';
import { SpringPhysics } from '@/effects/physics';
import { $$ } from '@/utils/dom';

export class MatrixController {
  private container: HTMLElement;
  private matrixEl: HTMLElement;
  private physicsX: SpringPhysics;
  private physicsY: SpringPhysics;
  private rafId: number | null = null;
  private animating = false;

  constructor(containerSelector = '.main-content') {
    this.container = document.querySelector(containerSelector) as HTMLElement;
    this.matrixEl = document.getElementById('workspace-matrix') as HTMLElement;

    if (!this.container || !this.matrixEl) {
      console.error('[MatrixController] Required DOM elements not found');
      return;
    }

    this.physicsX = new SpringPhysics(120, 20);
    this.physicsY = new SpringPhysics(120, 20);

    this.init();
  }

  private init(): void {
    this.physicsX.onUpdate((x) => stateMatrix.update('matrix', { x }));
    this.physicsY.onUpdate((y) => stateMatrix.update('matrix', { y }));

    this.bindKeyboard();
    this.bindDock();

    // 移动端不启动渲染循环
    if (!this.isMobile()) {
      this.startRenderLoop();
    }
  }

  private isMobile(): boolean {
    return window.innerWidth <= 768;
  }

  // === 按需渲染循环 (非永续) ===

  private startRenderLoop(): void {
    if (this.animating) return;
    this.animating = true;
    this.matrixEl.style.willChange = 'transform';
    this.tick();
  }

  private stopRenderLoop(): void {
    this.animating = false;
    this.matrixEl.style.willChange = 'auto';
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  private tick = (): void => {
    if (!this.animating) return;

    const { x, y } = stateMatrix.get('matrix');
    this.matrixEl.style.transform = `translate(${-x * 100}vw, ${-y * 100}vh)`;

    // 检查是否到达目标
    const { targetX, targetY } = stateMatrix.get('matrix');
    const settled =
      Math.abs(x - targetX) < 0.005 && Math.abs(y - targetY) < 0.005;

    if (settled) {
      // 吸附到精确位置
      this.matrixEl.style.transform = `translate(${-targetX * 100}vw, ${-targetY * 100}vh)`;
      stateMatrix.update('matrix', { isMoving: false });
      this.stopRenderLoop();
      return;
    }

    this.rafId = requestAnimationFrame(this.tick);
  };

  // === 导航 ===

  moveTo(nx: number, ny: number): void {
    if (nx < 0 || nx > 1 || ny < 0 || ny > 1) return;

    const { targetX, targetY } = stateMatrix.get('matrix');
    if (nx === targetX && ny === targetY) return; // 已在目标

    stateMatrix.update('matrix', { targetX: nx, targetY: ny, isMoving: true });

    if (this.isMobile()) {
      // 移动端: 直接跳转，不用物理动画
      this.physicsX.jumpTo(nx);
      this.physicsY.jumpTo(ny);
      stateMatrix.update('matrix', { x: nx, y: ny, isMoving: false });
      this.updateDock(nx, ny);
      this.updateActiveCell(nx, ny);
    } else {
      // 桌面端: 弹簧物理动画
      this.physicsX.setTarget(nx);
      this.physicsY.setTarget(ny);
      this.startRenderLoop();
      this.updateDock(nx, ny);
      this.updateActiveCell(nx, ny);
    }
  }

  jumpTo(nx: number, ny: number): void {
    if (nx < 0 || nx > 1 || ny < 0 || ny > 1) return;

    this.physicsX.jumpTo(nx);
    this.physicsY.jumpTo(ny);
    stateMatrix.update('matrix', {
      x: nx, y: ny, targetX: nx, targetY: ny, isMoving: false,
    });

    if (!this.isMobile()) {
      this.matrixEl.style.transform = `translate(${-nx * 100}vw, ${-ny * 100}vh)`;
      this.stopRenderLoop();
    }

    this.updateDock(nx, ny);
    this.updateActiveCell(nx, ny);
  }

  // === 键盘 ===

  private bindKeyboard(): void {
    document.addEventListener('keydown', (e) => {
      if (!e.ctrlKey) return;
      const { targetX, targetY } = stateMatrix.get('matrix');

      switch (e.key) {
        case 'ArrowUp':    e.preventDefault(); this.moveTo(targetX, targetY - 1); break;
        case 'ArrowDown':  e.preventDefault(); this.moveTo(targetX, targetY + 1); break;
        case 'ArrowLeft':  e.preventDefault(); this.moveTo(targetX - 1, targetY); break;
        case 'ArrowRight': e.preventDefault(); this.moveTo(targetX + 1, targetY); break;
      }
    });
  }

  // === Dock 栏 ===

  private bindDock(): void {
    $$('.dock-item').forEach((item) => {
      item.addEventListener('click', () => {
        const match = item.id.match(/dock-(\d)-(\d)/);
        if (match) {
          this.moveTo(parseInt(match[1]), parseInt(match[2]));
        }
      });
    });
  }

  private updateDock(nx: number, ny: number): void {
    $$('.dock-item').forEach((item) => {
      const isActive = item.id === `dock-${nx}-${ny}`;
      item.classList.toggle('active', isActive);
    });
  }

  private updateActiveCell(nx: number, ny: number): void {
    const targetId = `cell-${nx}-${ny}`;
    $$('.matrix-cell').forEach((cell) => {
      if (cell.id === targetId) {
        cell.classList.add('active-cell');
        cell.classList.remove('inactive-cell');
      } else {
        cell.classList.remove('active-cell');
        cell.classList.add('inactive-cell');
      }
    });
  }

  // === 清理 ===

  destroy(): void {
    this.stopRenderLoop();
  }
}
