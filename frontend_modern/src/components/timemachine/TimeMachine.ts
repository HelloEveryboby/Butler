/**
 * TimeMachine: 全局可观测时光机 (象限 1,0)
 *
 * 通过时间轴滑块重现系统历史快照。
 */

import { bridge } from '@/api';
import { toast } from '@/utils/toast';

interface Snapshot {
  timestamp: number;
  metrics: { cpu: number; memory: number; disk: number; network: number };
  events: string[];
}

export class TimeMachine {
  private container: HTMLElement | null = null;
  private snapshots: Snapshot[] = [];
  private currentIndex = 0;

  constructor() {
    this.container = document.getElementById('timemachine-content');
    if (this.container) {
      this.render();
      this.loadSnapshots();
    }
  }

  private render(): void {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="timemachine-controls">
        <input type="range" id="tm-slider" min="0" max="0" value="0" class="glass-input">
        <span id="tm-timestamp" class="text-muted text-sm"></span>
      </div>
      <div id="tm-metrics" class="timemachine-metrics"></div>
      <div id="tm-events" class="timemachine-events"></div>
    `;

    const slider = document.getElementById('tm-slider') as HTMLInputElement;
    if (slider) {
      slider.addEventListener('input', () => {
        this.currentIndex = parseInt(slider.value);
        this.renderSnapshot();
      });
    }
  }

  private async loadSnapshots(): Promise<void> {
    try {
      const data = await bridge.callSkill('system_monitor', 'snapshots');
      if (Array.isArray(data)) {
        this.snapshots = data;
        const slider = document.getElementById('tm-slider') as HTMLInputElement;
        if (slider) {
          slider.max = String(Math.max(0, this.snapshots.length - 1));
          slider.value = String(this.snapshots.length - 1);
          this.currentIndex = this.snapshots.length - 1;
        }
        this.renderSnapshot();
      }
    } catch {
      toast.warning('时光机', '无法加载历史快照');
    }
  }

  private renderSnapshot(): void {
    const snap = this.snapshots[this.currentIndex];
    if (!snap) return;

    const ts = document.getElementById('tm-timestamp');
    if (ts) ts.textContent = new Date(snap.timestamp).toLocaleString();

    const metrics = document.getElementById('tm-metrics');
    if (metrics) {
      metrics.innerHTML = `
        <div class="glass-card"><span>CPU</span><strong>${snap.metrics.cpu}%</strong></div>
        <div class="glass-card"><span>内存</span><strong>${snap.metrics.memory}%</strong></div>
        <div class="glass-card"><span>磁盘</span><strong>${snap.metrics.disk}%</strong></div>
        <div class="glass-card"><span>网络</span><strong>${snap.metrics.network} KB/s</strong></div>
      `;
    }

    const events = document.getElementById('tm-events');
    if (events) {
      events.innerHTML = snap.events
        .map((e) => `<div class="glass-card text-sm">${e}</div>`)
        .join('');
    }
  }
}
