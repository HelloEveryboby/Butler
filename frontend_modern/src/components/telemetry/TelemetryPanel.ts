/**
 * TelemetryPanel: 系统遥测面板
 *
 * 实时显示 CPU、内存、磁盘、网络指标。
 */

import { stateMatrix } from '@/stores/state-matrix';
import { bridge } from '@/api';

export class TelemetryPanel {
  private intervalId: ReturnType<typeof setInterval> | null = null;

  constructor() {
    this.startPolling();
  }

  private startPolling(): void {
    this.fetchMetrics();
    this.intervalId = setInterval(() => this.fetchMetrics(), 5000);
  }

  private async fetchMetrics(): Promise<void> {
    try {
      const data = await bridge.callSkill('system_monitor', 'metrics');
      if (data && typeof data === 'object') {
        const m = data as Record<string, number>;
        stateMatrix.update('metrics', {
          cpu: m.cpu ?? 0,
          memory: m.memory ?? 0,
          disk: m.disk ?? 0,
          network: m.network ?? 0,
        });
      }
    } catch {
      // 静默失败，遥测不是关键功能
    }
  }

  destroy(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }
}
