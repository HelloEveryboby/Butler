/**
 * Win11 单页路由 —— 取代 2x2 空间矩阵，保留 window.matrix.moveTo API。
 */

import { NAV_ITEMS, type NavItem } from './pages';

export class Win11Router {
  private current: string;
  private items: NavItem[] = NAV_ITEMS;

  constructor() {
    this.current = this.items[0]?.id || 'chat';
    this.bind();
    this.navigate(this.current, false);
  }

  private bind(): void {
    document.querySelectorAll<HTMLElement>('.nav-item[data-route]').forEach((item) => {
      item.addEventListener('click', () => {
        const route = item.dataset.route;
        if (route) this.navigate(route);
      });
    });

    window.addEventListener('keydown', (e: KeyboardEvent) => {
      if (!e.ctrlKey || e.metaKey) return;
      if (!e.key.startsWith('Arrow')) return;
      e.preventDefault();
      const index = this.items.findIndex((item) => item.id === this.current);
      const delta = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : -1;
      const next = this.items[(index + delta + this.items.length) % this.items.length];
      if (next) this.navigate(next.id);
    });

    window.addEventListener('keydown', (e: KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey) return;
      const index = Number(e.key) - 1;
      const target = this.items[index];
      if (target) {
        e.preventDefault();
        this.navigate(target.id);
      }
    });
  }

  public getCurrent(): string {
    return this.current;
  }

  /** 兼容旧矩阵 API：将 (x, y) 象限映射到对应页面。 */
  public moveTo(x: number, y: number): void {
    const target = this.items.find((item) => item.x === x && item.y === y);
    if (target) this.navigate(target.id);
  }

  public navigate(routeId: string, animate: boolean = true): void {
    const target = this.items.find((item) => item.id === routeId) || this.items[0];
    if (!target) return;
    this.current = target.id;

    document.querySelectorAll<HTMLElement>('.page-cell').forEach((page) => {
      const active = page.id === `cell-${target.x}-${target.y}`;
      page.classList.toggle('active', active);
      if (active && animate) {
        page.classList.remove('page-enter');
        void page.offsetWidth;
        page.classList.add('page-enter');
      }
    });

    document.querySelectorAll<HTMLElement>('.nav-item[data-route]').forEach((item) => {
      item.classList.toggle('active', item.dataset.route === target.id);
      if (item.dataset.route === target.id) {
        item.setAttribute('aria-current', 'page');
      } else {
        item.removeAttribute('aria-current');
      }
    });

    const state = window.stateMatrix;
    if (state) {
      state.update('matrix.x', target.x);
      state.update('matrix.y', target.y);
      state.update('matrix.targetX', target.x);
      state.update('matrix.targetY', target.y);
      state.update('matrix.isMoving', false);
    }

    document.body.dataset.route = target.id;
    window.dispatchEvent(new CustomEvent('butler:navigate', { detail: { route: target.id } }));
  }
}
