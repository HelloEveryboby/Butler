class DAGEngine {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.svg = document.getElementById('dag-svg');
        this.nodes = [];
        this.links = [];
        this.init();
    }

    init() {
        this.canvas.addEventListener('dragover', (e) => e.preventDefault());
        this.canvas.addEventListener('drop', (e) => this.handleDrop(e));

        window.addEventListener('resize', () => this.drawLinks());
    }

    handleDrop(e) {
        e.preventDefault();
        try {
            const data = JSON.parse(e.dataTransfer.getData('application/json'));
            if (data.type === 'skill') {
                const rect = this.canvas.getBoundingClientRect();
                this.addNode(data, e.clientX - rect.left - 60, e.clientY - rect.top - 30);
            }
        } catch (err) {}
    }

    addNode(skill, x, y) {
        const node = document.createElement('div');
        node.className = 'dag-node glass-surface damping-transition';
        node.style.left = `${x}px`;
        node.style.top = `${y}px`;
        node.innerHTML = `
            <div class="node-input-slot"></div>
            <i class="fas ${skill.icon || 'fa-puzzle-piece'}"></i>
            <span>${skill.name}</span>
            <div class="node-output-slot" draggable="true"></div>
        `;

        this.canvas.appendChild(node);
        this.nodes.push(node);
        this.makeDraggable(node);
        this.canvas.querySelector('.canvas-placeholder').style.display = 'none';
    }

    makeDraggable(node) {
        let offsetX, offsetY;
        node.onmousedown = (e) => {
            if (e.target.classList.contains('node-output-slot')) return;
            offsetX = e.clientX - node.offsetLeft;
            offsetY = e.clientY - node.offsetTop;
            document.onmousemove = (e) => {
                node.style.left = `${e.clientX - offsetX}px`;
                node.style.top = `${e.clientY - offsetY}px`;
                this.drawLinks();
            };
            document.onmouseup = () => {
                document.onmousemove = null;
            };
        };

        const output = node.querySelector('.node-output-slot');
        output.onmousedown = (e) => {
            e.stopPropagation();
            // Link logic would go here
        };
    }

    drawLinks() {
        this.svg.innerHTML = '';
        // Placeholder for real link drawing
        // If nodes 0 and 1 exist, draw a mock line
        if (this.nodes.length >= 2) {
            this.createLink(this.nodes[0], this.nodes[1]);
        }
    }

    createLink(from, to) {
        const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const x1 = from.offsetLeft + from.offsetWidth;
        const y1 = from.offsetTop + from.offsetHeight / 2;
        const x2 = to.offsetLeft;
        const y2 = to.offsetTop + to.offsetHeight / 2;

        const cp1 = x1 + 50;
        const cp2 = x2 - 50;

        line.setAttribute("d", `M ${x1} ${y1} C ${cp1} ${y1}, ${cp2} ${y2}, ${x2} ${y2}`);
        line.setAttribute("stroke", "#007AFF");
        line.setAttribute("stroke-width", "2");
        line.setAttribute("fill", "none");
        line.style.filter = "drop-shadow(0 0 5px #007AFF)";
        this.svg.appendChild(line);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.dag = new DAGEngine('workflow-canvas');
});
