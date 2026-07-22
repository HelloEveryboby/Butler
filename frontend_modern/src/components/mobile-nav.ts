/**
 * 移动端导航控制器 (性能优化版)
 *
 * - 滑动手势用 passive 监听
 * - Tab 切换直接 display:none/block，无动画开销
 * - 状态同步最小化
 */

import { stateMatrix } from '@/stores/state-matrix';

type Quadrant = '0,0' | '1,0' | '0,1' | '1,1';
const TAB_ORDER: Quadrant[] = ['0,0', '1,0', '0,1', '1,1'];

export class MobileNav {
  private isMobile = false;
  private currentTab: Quadrant = '0,0';
  private startX = 0;
  private startY = 0;

  constructor() {
    this.checkMode();
    this.bindResize();
    this.bindDock();
    this.bindSwipe();
    this.initTab();
  }

  get mobile(): boolean { return this.isMobile; }
  get current(): Quadrant { return this.currentTab; }

  private checkMode(): void {
    this.isMobile = window.innerWidth <= 768;
    document.body.classList.toggle('interface-mobile', this.isMobile);
    document.body.classList.toggle('interface-desktop', !this.isMobile);
  }

  private bindResize(): void {
    let timer: ReturnType<typeof setTimeout>;
    window.addEventListener('resize', () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const was = this.isMobile;
        this.checkMode();
        if (was !== this.isMobile) this.initTab();
      }, 200);
    }, { passive: true });
  }

  private bindDock(): void {
    document.querySelectorAll('.dock-item').forEach((item) => {
      item.addEventListener('click', () => {
        const m = item.id.match(/dock-(\d)-(\d)/);
        if (m) this.switchTab(`${m[1]},${m[2]}` as Quadrant);
      });
    });
  }

  private bindSwipe(): void {
    const el = document.querySelector('.main-content');
    if (!el) return;

    el.addEventListener('touchstart', (e: Event) => {
      const t = (e as TouchEvent).touches[0];
      this.startX = t.clientX;
      this.startY = t.clientY;
    }, { passive: true });

    el.addEventListener('touchend', (e: Event) => {
      const t = (e as TouchEvent).changedTouches[0];
      const dx = t.clientX - this.startX;
      const dy = t.clientY - this.startY;

      if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;

      const idx = TAB_ORDER.indexOf(this.currentTab);
      if (dx < 0 && idx < TAB_ORDER.length - 1) {
        this.switchTab(TAB_ORDER[idx + 1]);
      } else if (dx > 0 && idx > 0) {
        this.switchTab(TAB_ORDER[idx - 1]);
      }
    }, { passive: true });
  }

  private initTab(): void {
    if (this.isMobile) {
      this.switchTab('0,0');
    } else {
      document.querySelectorAll('.matrix-cell').forEach((c) => {
        c.classList.add('active-cell');
      });
    }
  }

  switchTab(tab: Quadrant): void {
    if (!this.isMobile || tab === this.currentTab) return;

    this.currentTab = tab;
    const [x, y] = tab.split(',').map(Number);

    // 直接切换 display，无动画
    document.querySelectorAll('.matrix-cell').forEach((c) => {
      c.classList.remove('active-cell');
    });
    document.getElementById(`cell-${x}-${y}`)?.classList.add('active-cell');

    // Dock 高亮
    document.querySelectorAll('.dock-item').forEach((item) => {
      item.classList.toggle('active', item.id === `dock-${x}-${y}`);
    });

    // 状态同步 (最小化)
    stateMatrix.update('matrix', { targetX: x, targetY: y });

    window.scrollTo(0, 0);
  }

  moveTo(nx: number, ny: number): void {
    if (this.isMobile) this.switchTab(`${nx},${ny}` as Quadrant);
  }
}
