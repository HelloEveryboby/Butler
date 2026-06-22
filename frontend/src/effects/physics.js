/**
 * Lightweight Spring Physics Engine for Butler UI.
 * Zero-dependency implementation of Hooke's Law with Damping.
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
    }

    setTarget(v) {
        this.target = v;
        this.start();
    }

    setCurrent(v) {
        this.x = v;
    }

    start() {
        if (this.animating) return;
        this.animating = true;
        this.lastTime = performance.now();
        this.update();
    }

    update() {
        if (!this.animating) return;

        const now = performance.now();
        const dt = (now - this.lastTime) / 1000; // to seconds
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
        if (Math.abs(this.v) < 0.01 && Math.abs(this.x - this.target) < 0.01) {
            this.x = this.target;
            this.v = 0;
            this.animating = false;
            this.listeners.forEach(fn => fn(this.x));
            return;
        }

        requestAnimationFrame(() => this.update());
    }

    onUpdate(fn) {
        this.listeners.push(fn);
    }
}

// Example: Apply spring to sidebar or modal
// const sidebarSpring = new SpringPhysics(200, 20);
// sidebarSpring.onUpdate(x => sidebar.style.transform = `translateX(${x}px)`);
