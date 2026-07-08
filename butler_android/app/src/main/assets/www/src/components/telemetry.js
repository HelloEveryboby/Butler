/**
 * Butler Telemetry: Connects to the backend WebSocket and updates StateMatrix.
 */
class ButlerTelemetry {
    constructor(url = 'ws://localhost:8000') {
        this.url = url;
        this.socket = null;
        this.reconnectInterval = 5000;
        this.connect();
    }

    connect() {
        console.log(`📡 Connecting to Telemetry: ${this.url}`);
        this.socket = new WebSocket(this.url);

        this.socket.onopen = () => {
            console.log("✅ Telemetry Connected");
            this.socket.send(JSON.stringify({
                type: 'register',
                runner_id: 'butler_ui',
                token: 'BUTLER_SECRET_2026' // Should be dynamic in production
            }));
        };

        this.socket.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'metrics') {
                    window.stateMatrix.update('metrics.cpu', msg.data.cpu);
                    window.stateMatrix.update('metrics.memory', msg.data.memory);
                    if (msg.data.disk) window.stateMatrix.update('metrics.disk', msg.data.disk);
                    if (msg.data.network) window.stateMatrix.update('metrics.network', msg.data.network);
                }
            } catch (e) {
                console.error("Telemetry parse error", e);
            }
        };

        this.socket.onclose = () => {
            console.warn("⚠️ Telemetry Disconnected. Reconnecting...");
            setTimeout(() => this.connect(), this.reconnectInterval);
        };

        this.socket.onerror = (err) => {
            console.error("Telemetry error", err);
            this.socket.close();
        };
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.telemetry = new ButlerTelemetry();
});
