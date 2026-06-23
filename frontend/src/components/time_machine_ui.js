class TimeMachineUI {
    constructor() {
        this.slider = document.getElementById('global-tm-slider');
        this.metrics = document.getElementById('tm-metrics');
        this.logs = document.getElementById('tm-logs');
        this.timeLabel = document.querySelector('.tm-time-label');

        this.init();
    }

    init() {
        this.slider.addEventListener('input', (e) => {
            const val = e.target.value;
            this.update(val);
        });
    }

    update(val) {
        const offset = (100 - val) * 60; // Up to 60 mins back
        const ts = Date.now() - offset * 1000;
        const date = new Date(ts);

        this.timeLabel.innerText = val == 100 ? "现在" : date.toLocaleTimeString();

        // Visual feedback
        if (val < 100) {
            document.body.classList.add('tm-active');
        } else {
            document.body.classList.remove('tm-active');
        }

        // Mock: Highlighting errors in logs if val matches a crash point
        if (val == 30) {
            this.showCrashState();
        } else {
            this.clearCrashState();
        }
    }

    showCrashState() {
        document.querySelectorAll('.matrix-cell').forEach(cell => {
            cell.style.boxShadow = "inset 0 0 50px rgba(255, 59, 48, 0.3)";
        });
        this.logs.innerHTML = '<div class="interaction-line ai-output-line" style="border-color: #FF3B30; color: #FF3B30;">[ERROR] 15:30:22 - Socket hang up. Port 8080 lost.</div>';
    }

    clearCrashState() {
        document.querySelectorAll('.matrix-cell').forEach(cell => {
            cell.style.boxShadow = "none";
        });
        this.logs.innerHTML = '<div class="interaction-line ai-output-line">系统运行正常。</div>';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.timeMachine = new TimeMachineUI();
});
