class SubstrateHeatmap {
    constructor() {
        this.canvas = document.getElementById('substrate-heatmap');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.canvas.width = this.width;
        this.canvas.height = this.height;

        this.cpuValue = 0.1; // 0 to 1
        this.memValue = 0.1; // 0 to 1

        this.particles = [];
        this.initParticles();
        this.animate();

        window.addEventListener('resize', () => this.onResize());
        this.connectMetricsStream();
    }

    onResize() {
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.canvas.width = this.width;
        this.canvas.height = this.height;
    }

    initParticles() {
        const count = 50;
        for (let i = 0; i < count; i++) {
            this.particles.push({
                x: Math.random() * this.width,
                y: Math.random() * this.height,
                size: Math.random() * 300 + 100,
                vx: Math.random() * 2 - 1,
                vy: Math.random() * 2 - 1,
                color: { r: 0, g: 100, b: 255, a: 0.1 }
            });
        }
    }

    connectMetricsStream() {
        // Use WebSocket for real-time low-latency updates
        const socket = new WebSocket('ws://localhost:8000');

        socket.onopen = () => {
            // Register as UI client (using a mock token for verification, normally secure)
            socket.send(JSON.stringify({
                type: 'register',
                runner_id: 'butler_ui',
                token: 'BUTLER_SECRET_2026'
            }));
        };

        socket.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'metrics') {
                this.updateMetrics(msg.data.cpu, msg.data.memory);
            }
        };

        // Polling as a fallback if WebSocket fails or for robustness
        setInterval(async () => {
            if (socket.readyState !== WebSocket.OPEN) {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.get_realtime_metrics) {
                    try {
                        const stats = await window.pywebview.api.get_realtime_metrics();
                        if (stats) {
                            this.updateMetrics(stats.cpu, stats.memory);
                        }
                    } catch (e) {
                        console.error("Failed to fetch metrics", e);
                    }
                }
            }
        }, 1000);
    }

    updateMetrics(cpu, mem) {
        this.cpuValue = cpu / 100;
        this.memValue = mem / 100;
    }

    animate() {
        this.ctx.clearRect(0, 0, this.width, this.height);

        // Speed and color based on metrics
        const speedFactor = 0.5 + this.cpuValue * 5;
        const densityFactor = 1 + this.memValue * 3;

        this.particles.forEach(p => {
            p.x += p.vx * speedFactor;
            p.y += p.vy * speedFactor;

            if (p.x < -p.size) p.x = this.width + p.size;
            if (p.x > this.width + p.size) p.x = -p.size;
            if (p.y < -p.size) p.y = this.height + p.size;
            if (p.y > this.height + p.size) p.y = -p.size;

            // Gradient color based on CPU (Blue -> Orange/Red)
            const r = Math.floor(0 + this.cpuValue * 255);
            const g = Math.floor(100 + this.cpuValue * 50);
            const b = Math.floor(255 - this.cpuValue * 200);

            const gradient = this.ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size);
            gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${0.1 * densityFactor})`);
            gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);

            this.ctx.fillStyle = gradient;
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            this.ctx.fill();
        });

        requestAnimationFrame(() => this.animate());
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.heatmap = new SubstrateHeatmap();
});
