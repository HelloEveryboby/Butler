/**
 * Lightweight Spring Physics Engine for Butler UI.
 * Zero-dependency implementation of Hooke's Law with Damping.
 * Optimized for StateMatrix synchronization.
 */
class SpringPhysics {
    constructor(stiffness = 170, damping = 26, mass = 1) {
        this.k = stiffness;
        this.c = damping;
        this.m = mass;

        this.x = 0;       // Current position
        this.v = 0;       // Current velocity
        this.target = 0;  // Target position

        this.listeners = [];
        this.animating = false;
    }

    setTarget(v) {
        this.target = v;
        if (!this.animating) {
            this.start();
        }
    }

    setCurrent(v) {
        this.x = v;
    }

    start() {
        this.animating = true;
        this.lastTime = performance.now();
        this.updateFrame();
    }

    updateFrame() {
        if (!this.animating) return;

        const now = performance.now();
        const dt = Math.min((now - this.lastTime) / 1000, 0.1); // caps dt to avoid huge jumps
        this.lastTime = now;

        // 4 lines of Spring Physics (Hooke's Law + Damping)
        const fSpring = -this.k * (this.x - this.target);
        const fDamper = -this.c * this.v;
        const a = (fSpring + fDamper) / this.m;

        this.v += a * dt;
        this.x += this.v * dt;

        // Notify listeners
        this.listeners.forEach(fn => fn(this.x));

        // Stop condition: low velocity and close to target
        if (Math.abs(this.v) < 0.001 && Math.abs(this.x - this.target) < 0.001) {
            this.x = this.target;
            this.v = 0;
            this.animating = false;
            return;
        }

        requestAnimationFrame(() => this.updateFrame());
    }

    onUpdate(fn) {
        this.listeners.push(fn);
    }
}

window.SpringPhysics = SpringPhysics;
