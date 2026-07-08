class MatrixWormhole {
    constructor() {
        this.gates = document.querySelectorAll('.wormhole-gate');
        this.isDragging = false;
        this.draggedElement = null;

        this.init();
    }

    init() {
        document.addEventListener('dragstart', (e) => this.onDragStart(e));
        document.addEventListener('drag', (e) => this.onDrag(e));
        document.addEventListener('dragend', (e) => this.onDragEnd(e));

        this.gates.forEach(gate => {
            gate.addEventListener('dragover', (e) => {
                e.preventDefault();
                gate.classList.add('pulling');
            });
            gate.addEventListener('dragleave', () => {
                gate.classList.remove('pulling');
            });
            gate.addEventListener('drop', (e) => this.onDrop(e, gate));
        });
    }

    onDragStart(e) {
        if (e.target.classList.contains('skill-card') || e.target.closest('.skill-card')) {
            this.isDragging = true;
            this.draggedElement = e.target.closest('.skill-card');
            this.showGates();
        }
    }

    onDrag(e) {
        if (!this.isDragging) return;
        // Optional: distance-based gate highlighting
    }

    onDragEnd(e) {
        this.isDragging = false;
        this.hideGates();
    }

    showGates() {
        this.gates.forEach(gate => gate.classList.add('active'));
    }

    hideGates() {
        this.gates.forEach(gate => gate.classList.remove('active', 'pulling'));
    }

    async onDrop(e, gate) {
        e.preventDefault();
        const targetQuadrant = gate.dataset.quadrant; // e.g. "0,1"
        const [qx, qy] = targetQuadrant.split(',').map(Number);

        if (this.draggedElement) {
            // Suction animation
            this.draggedElement.classList.add('key-dissolve'); // Reuse dissolve animation

            setTimeout(() => {
                // Logic to "transport" the element
                const skillId = this.draggedElement.dataset.skillId;
                this.transportSkill(skillId, qx, qy);

                if (this.draggedElement.parentNode) {
                    this.draggedElement.parentNode.removeChild(this.draggedElement);
                }
                this.draggedElement = null;
            }, 800);
        }
    }

    transportSkill(skillId, qx, qy) {
        // Move view to target quadrant
        if (window.matrix) {
            window.matrix.moveTo(qx, qy);
        }

        // If target is DAG (0,1), instantiate the skill node
        if (qx === 0 && qy === 1 && window.dagEngine) {
            window.dagEngine.addNode(skillId);
        }

        // Visual feedback in target quadrant (pop-in)
        console.log(`Skill ${skillId} transported to (${qx}, ${qy})`);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.wormhole = new MatrixWormhole();
});
