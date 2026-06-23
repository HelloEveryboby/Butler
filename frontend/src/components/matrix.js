class MatrixController {
    constructor() {
        this.container = document.querySelector('.main-content');
        this.matrix = document.getElementById('workspace-matrix');
        this.x = 0;
        this.y = 0;
        this.isMoving = false;

        this.init();
    }

    init() {
        window.addEventListener('keydown', (e) => {
            if (e.ctrlKey) {
                switch(e.key) {
                    case 'ArrowUp': this.moveTo(this.x, this.y - 1); break;
                    case 'ArrowDown': this.moveTo(this.x, this.y + 1); break;
                    case 'ArrowLeft': this.moveTo(this.x - 1, this.y); break;
                    case 'ArrowRight': this.moveTo(this.x + 1, this.y); break;
                }
            }
        });

        // Touch swiping logic (simplified)
        let touchStartX = 0;
        let touchStartY = 0;
        this.container.addEventListener('touchstart', e => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        }, { passive: true });

        this.container.addEventListener('touchend', e => {
            const dx = e.changedTouches[0].clientX - touchStartX;
            const dy = e.changedTouches[0].clientY - touchStartY;
            if (Math.abs(dx) > 100 || Math.abs(dy) > 100) {
                if (Math.abs(dx) > Math.abs(dy)) {
                    this.moveTo(this.x - Math.sign(dx), this.y);
                } else {
                    this.moveTo(this.x, this.y - Math.sign(dy));
                }
            }
        }, { passive: true });
    }

    moveTo(nx, ny) {
        if (nx < 0 || nx > 1 || ny < 0 || ny > 1 || this.isMoving) return;

        this.x = nx;
        this.y = ny;
        this.isMoving = true;

        // Final coordinate system mapping:
        // (0,0): Smart Chat (Col 1, Row 1) -> transform(0, 0)
        // (0,1): DAG (Col 2, Row 1)        -> transform(-100vw, 0)
        // (1,0): Time Machine (Col 1, Row 2) -> transform(0, -100vh)
        // (1,1): Skills (Col 2, Row 2)     -> transform(-100vw, -100vh)

        // Based on the HTML IDs and Dock buttons:
        // dock-0-0 -> (0,0)
        // dock-0-1 -> (0,1)
        // dock-1-0 -> (1,0)
        // dock-1-1 -> (1,1)

        // So nx is X (Column index 0 or 1), ny is Y (Row index 0 or 1).
        const translateX = -nx * 100;
        const translateY = -ny * 100;

        this.matrix.style.transform = `translate(${translateX}vw, ${translateY}vh)`;

        // Update Dock active state
        this.updateDock();

        setTimeout(() => { this.isMoving = false; }, 600);
    }

    updateDock() {
        const dockItems = document.querySelectorAll('.dock-item');
        dockItems.forEach(item => item.classList.remove('active'));
        const targetId = `dock-${this.x}-${this.y}`;
        const target = document.getElementById(targetId);
        if (target) target.classList.add('active');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.matrix = new MatrixController();
});
