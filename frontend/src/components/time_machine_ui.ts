/**
 * Butler TimeMachine UI: Frosted glass timeline slider and historical 回溯.
 */

class TimeMachineUI {
  public slider: HTMLInputElement | null;
  public label: HTMLElement | null;
  public metricsContainer: HTMLElement | null;
  public logsContainer: HTMLElement | null;
  public isReplaying: boolean = false;

  constructor() {
    this.slider = document.getElementById('global-tm-slider') as HTMLInputElement;
    this.label = document.querySelector('.tm-time-label');
    this.metricsContainer = document.getElementById('tm-metrics');
    this.logsContainer = document.getElementById('tm-logs');

    this.init();
  }

  public init(): void {
    if (!this.slider) return;

    this.slider.addEventListener('input', (e: Event) => {
      const target = e.target as HTMLInputElement;
      const val = parseInt(target.value, 10);
      this.updateLabel(val);

      if (val < 100) {
        this.enterReplayMode(val);
      } else {
        this.exitReplayMode();
      }
    });

    this.initMetricsCanvas();
  }

  public updateLabel(val: number): void {
    if (!this.label) return;
    if (val === 100) {
      this.label.innerText = '现在 (实时模式)';
      this.label.style.color = 'var(--accent-color)';
    } else {
      const minutesAgo = 100 - val;
      this.label.innerText = `${minutesAgo} 分钟前`;
      this.label.style.color = '#FF9500';
    }
  }

  public async enterReplayMode(val: number): Promise<void> {
    if (!this.isReplaying) {
      this.isReplaying = true;
      document.body.classList.add('tm-active');
      window.stateMatrix?.update('timemachine.active', true);
    }

    const now = Date.now() / 1000;
    const targetTs = now - (100 - val) * 60;

    if (window.pywebview && window.pywebview.api) {
      const snapshot = await window.pywebview.api.get_time_machine_range(targetTs - 10, targetTs + 10);
      if (snapshot && snapshot.length > 0) {
        this.renderSnapshot(snapshot[0]);
      }
    }
  }

  public exitReplayMode(): void {
    this.isReplaying = false;
    document.body.classList.remove('tm-active');
    window.stateMatrix?.update('timemachine.active', false);
    if (this.label) {
      this.label.innerText = '现在 (实时模式)';
    }
  }

  public renderSnapshot(data: any): void {
    console.log('Replaying Snapshot:', data);
    if (data && data.category === 'system_snapshot' && this.logsContainer) {
      const stats = data.data?.system || {};
      this.logsContainer.innerHTML =
        `<div class="tm-log-entry" style="color: #FF9500;">[SNAPSHOT] 系统状态: CPU ${stats.cpu || 0}%, MEM ${stats.memory || 0}%</div>` +
        this.logsContainer.innerHTML;
    }
  }

  public pushLog(data: any): void {
    if (!this.logsContainer) return;
    const timeStr = new Date().toLocaleTimeString();
    const logEl = document.createElement('div');
    logEl.className = 'tm-log-entry';
    logEl.innerText = `[${timeStr}] ${typeof data === 'string' ? data : JSON.stringify(data)}`;
    this.logsContainer.insertBefore(logEl, this.logsContainer.firstChild);
  }

  public initMetricsCanvas(): void {
    if (!this.metricsContainer) return;
    this.metricsContainer.innerHTML = `
      <div style="padding: 20px; color: var(--text-secondary); font-size: 12px; text-align: center;">
        <i class="fas fa-chart-line" style="font-size: 40px; opacity: 0.1; margin-bottom: 10px; display: block;"></i>
        历史资源负载视图
      </div>
    `;
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    const tm = new TimeMachineUI();
    (window as any).timeMachineUI = tm;
    window.timeMachine = tm;
    (window as any).TimeMachine = tm;
    (window as any).TimeMachineUI = TimeMachineUI;
  });
}
