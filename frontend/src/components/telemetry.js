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

                    // Handle diagnostic telemetry in Header
                    if (msg.data.diagnostics) {
                        const d = msg.data.diagnostics;
                        // 1. Vector Memory DB Indicator
                        const vDbText = document.getElementById("vector-db-text");
                        const vDbInd = document.getElementById("vector-db-indicator");
                        if (vDbText && vDbInd) {
                            vDbText.innerText = d.vector_level || "SQLite";
                            vDbInd.className = "indicator-dot";
                            if (d.vector_level === "Redis") {
                                vDbInd.classList.add("green");
                            } else if (d.vector_level === "Zvec") {
                                vDbInd.classList.add("yellow");
                            } else {
                                vDbInd.classList.add("gray");
                            }
                        }

                        // 2. BHL Binary Heartbeat pulse
                        const bhlText = document.getElementById("bhl-heartbeat-text");
                        const bhlInd = document.getElementById("bhl-heartbeat-indicator");
                        if (bhlText && bhlInd) {
                            const isReady = d.bhl_statuses && Object.values(d.bhl_statuses).some(s => s === "Ready");
                            bhlText.innerText = isReady ? "BHL: Active" : "BHL: Offline";
                            bhlInd.className = "indicator-dot " + (isReady ? "green" : "gray");
                        }

                        // 3. Mounted Storage text
                        const cloudText = document.getElementById("cloud-storage-text");
                        if (cloudText && d.cloud_drives) {
                            cloudText.innerText = Array.isArray(d.cloud_drives) ? d.cloud_drives.join(', ') : d.cloud_drives;
                        }
                    }
                } else if (msg.type === "quota_state" || msg.type === "dream_state") {
                    if (msg.type === "quota_state") {
                        if (typeof window.updateQuotaExhaustedState === "function") {
                            window.updateQuotaExhaustedState(msg.payload === "quota_exhausted");
                        }
                    } else if (msg.type === "dream_state") {
                        if (typeof window.updateDreamingState === "function") {
                            window.updateDreamingState(msg.payload === "dreaming_start");
                        }
                    }
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
