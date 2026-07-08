class SubstrateHeatmap {
    constructor() {
        this.canvas = document.getElementById('substrate-heatmap');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.onResize();

        this.particles = [];
        this.initParticles();
        this.animate();

        window.addEventListener('resize', () => this.onResize());
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
                vy: Math.random() * 2 - 1
            });
        }
    }

    animate() {
        this.ctx.clearRect(0, 0, this.width, this.height);

        // Pull metrics from StateMatrix (One-way pull)
        const cpu = window.stateMatrix.get('metrics.cpu') || 0;
        const mem = window.stateMatrix.get('metrics.memory') || 0;

        const cpuValue = cpu / 100;
        const memValue = mem / 100;

        const speedFactor = 0.5 + cpuValue * 5;
        const densityFactor = 1 + memValue * 3;

        this.particles.forEach(p => {
            p.x += p.vx * speedFactor;
            p.y += p.vy * speedFactor;

            if (p.x < -p.size) p.x = this.width + p.size;
            if (p.x > this.width + p.size) p.x = -p.size;
            if (p.y < -p.size) p.y = this.height + p.size;
            if (p.y > this.height + p.size) p.y = -p.size;

            const r = Math.floor(0 + cpuValue * 255);
            const g = Math.floor(100 + cpuValue * 50);
            const b = Math.floor(255 - cpuValue * 200);

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
