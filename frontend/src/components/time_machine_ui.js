/**
 * Butler TimeMachine UI: Frosted glass timeline slider and historical回溯.
 */
class TimeMachineUI {
    constructor() {
        this.slider = document.getElementById('global-tm-slider');
        this.label = document.querySelector('.tm-time-label');
        this.metricsContainer = document.getElementById('tm-metrics');
        this.logsContainer = document.getElementById('tm-logs');

        this.isReplaying = false;
        this.init();
    }

    init() {
        if (!this.slider) return;

        this.slider.addEventListener('input', (e) => {
            const val = parseInt(e.target.value);
            this.updateLabel(val);

            if (val < 100) {
                this.enterReplayMode(val);
            } else {
                this.exitReplayMode();
            }
        });

        // Initialize Metrics Canvas
        this.initMetricsCanvas();
    }

    updateLabel(val) {
        if (val === 100) {
            this.label.innerText = "现在 (实时模式)";
            this.label.style.color = "var(--accent-color)";
        } else {
            const minutesAgo = 100 - val;
            this.label.innerText = `${minutesAgo} 分钟前`;
            this.label.style.color = "#FF9500";
        }
    }

    async enterReplayMode(val) {
        if (!this.isReplaying) {
            this.isReplaying = true;
            document.body.classList.add('tm-active');
            window.stateMatrix.update('timemachine.active', true);
        }

        // Fetch historical snapshot from backend
        const now = Date.now() / 1000;
        const targetTs = now - (100 - val) * 60;

        if (window.pywebview && window.pywebview.api) {
            const snapshot = await window.pywebview.api.get_time_machine_range(targetTs - 10, targetTs + 10);
            if (snapshot && snapshot.length > 0) {
                this.renderSnapshot(snapshot[0]);
            }
        }
    }

    exitReplayMode() {
        this.isReplaying = false;
        document.body.classList.remove('tm-active');
        window.stateMatrix.update('timemachine.active', false);
        this.label.innerText = "现在 (实时模式)";
        // Restore current metrics UI
    }

    renderSnapshot(data) {
        // Update UI components to reflect past state
        console.log("Replaying Snapshot:", data);
        if (data.category === 'system_snapshot') {
            const stats = data.data.system;
            // Highlight metrics
            this.logsContainer.innerHTML = `<div class="tm-log-entry" style="color: #FF9500;">[SNAPSHOT] 系统状态: CPU ${stats.cpu}%, MEM ${stats.memory}%</div>` + this.logsContainer.innerHTML;
        }
    }

    initMetricsCanvas() {
        // Placeholder for sparkline or mini chart
        this.metricsContainer.innerHTML = `
            <div style="padding: 20px; color: var(--text-secondary); font-size: 12px; text-align: center;">
                <i class="fas fa-chart-line" style="font-size: 40px; opacity: 0.1; margin-bottom: 10px; display: block;"></i>
                历史资源负载视图
            </div>
        `;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.timeMachineUI = new TimeMachineUI();
});
