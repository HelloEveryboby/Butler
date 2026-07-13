/**
 * Butler DAG Engine: SVG-based connection lines and draggable skill nodes.
 */
class DAGEngine {
    constructor() {
        this.canvas = document.getElementById('workflow-canvas');
        this.svg = document.getElementById('dag-svg');
        this.nodes = [];
        this.connections = [];
        this.isConnecting = false;
        this.tempLine = null;
        this.isRunning = false;

        this.init();
    }

    init() {
        this.canvas.addEventListener('dragover', (e) => e.preventDefault());
        this.canvas.addEventListener('drop', (e) => this.onDrop(e));

        // SVG Mouse tracking for temp connection lines
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));

        // Render loop
        const render = () => {
            this.updateConnections();
            requestAnimationFrame(render);
        };
        requestAnimationFrame(render);
    }

    onDrop(e) {
        e.preventDefault();
        const dataStr = e.dataTransfer.getData('application/json');
        if (!dataStr) return;

        const data = JSON.parse(dataStr);
        if (data.type === 'skill') {
            const rect = this.canvas.getBoundingClientRect();
            this.addNode(data.name, data.icon, e.clientX - rect.left - 60, e.clientY - rect.top - 30);

            // Hide placeholder
            const placeholder = this.canvas.querySelector('.canvas-placeholder');
            if (placeholder) placeholder.style.display = 'none';
        }
    }

    addNode(name, icon, x, y) {
        const node = document.createElement('div');
        node.className = 'dag-node glass-surface damping-transition';
        node.style.left = `${x}px`;
        node.style.top = `${y}px`;

        const nodeId = `node-${Date.now()}`;
        node.id = nodeId;
        node.dataset.skillId = name;

        node.innerHTML = `
            <div class="node-input-slot" data-node-id="${nodeId}"></div>
            <i class="fas ${icon}"></i>
            <span>${name}</span>
            <div class="node-output-slot" data-node-id="${nodeId}"></div>
        `;

        this.canvas.appendChild(node);
        this.makeDraggable(node);

        // Connector logic
        node.querySelector('.node-output-slot').addEventListener('mousedown', (e) => this.startConnection(e, nodeId));
        node.querySelector('.node-input-slot').addEventListener('mouseup', (e) => this.endConnection(e, nodeId));

        this.nodes.push({ id: nodeId, el: node });
    }

    makeDraggable(el) {
        let isDragging = false;
        let startX, startY;

        el.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('node-output-slot') || e.target.classList.contains('node-input-slot')) return;
            isDragging = true;
            startX = e.clientX - el.offsetLeft;
            startY = e.clientY - el.offsetTop;
            el.style.transition = 'none';
            el.classList.add('dragging');
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            el.style.left = `${e.clientX - startX}px`;
            el.style.top = `${e.clientY - startY}px`;
        });

        document.addEventListener('mouseup', () => {
            if (!isDragging) return;
            isDragging = false;
            el.style.transition = '';
            el.classList.remove('dragging');
        });
    }

    startConnection(e, nodeId) {
        e.stopPropagation();
        this.isConnecting = true;
        const rect = e.target.getBoundingClientRect();
        const canvasRect = this.canvas.getBoundingClientRect();

        this.tempLine = {
            from: nodeId,
            startX: rect.left + rect.width / 2 - canvasRect.left,
            startY: rect.top + rect.height / 2 - canvasRect.top
        };
    }

    endConnection(e, nodeId) {
        if (this.isConnecting && this.tempLine && this.tempLine.from !== nodeId) {
            this.connections.push({
                from: this.tempLine.from,
                to: nodeId
            });
        }
        this.isConnecting = false;
        this.tempLine = null;
        this.svg.innerHTML = ''; // Clear temp lines
    }

    onMouseMove(e) {
        if (this.isConnecting && this.tempLine) {
            const canvasRect = this.canvas.getBoundingClientRect();
            this.drawTempLine(
                this.tempLine.startX,
                this.tempLine.startY,
                e.clientX - canvasRect.left,
                e.clientY - canvasRect.top
            );
        }
    }

    drawTempLine(x1, y1, x2, y2) {
        this.svg.innerHTML = ''; // Inefficient but fine for one temp line
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const d = `M ${x1} ${y1} C ${x1 + 50} ${y1}, ${x2 - 50} ${y2}, ${x2} ${y2}`;
        path.setAttribute('d', d);
        path.setAttribute('stroke', 'var(--accent-color)');
        path.setAttribute('stroke-width', '2');
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke-dasharray', '5,5');
        this.svg.appendChild(path);
    }

    updateConnections() {
        if (this.connections.length === 0 && !this.isConnecting) {
            this.svg.innerHTML = '';
            return;
        }

        let html = '';
        const canvasRect = this.canvas.getBoundingClientRect();

        this.connections.forEach(conn => {
            const fromNode = document.getElementById(conn.from);
            const toNode = document.getElementById(conn.to);
            if (!fromNode || !toNode) return;

            const fromOut = fromNode.querySelector('.node-output-slot').getBoundingClientRect();
            const toIn = toNode.querySelector('.node-input-slot').getBoundingClientRect();

            const x1 = fromOut.left + fromOut.width / 2 - canvasRect.left;
            const y1 = fromOut.top + fromOut.height / 2 - canvasRect.top;
            const x2 = toIn.left + toIn.width / 2 - canvasRect.left;
            const y2 = toIn.top + toIn.height / 2 - canvasRect.top;

            const runningClass = this.isRunning ? 'running-flow' : '';
            html += `<path class="dag-svg-path ${runningClass}" d="M ${x1} ${y1} C ${x1 + 50} ${y1}, ${x2 - 50} ${y2}, ${x2} ${y2}"
                           stroke="var(--accent-color)" stroke-width="2.5" fill="none" />`;
        });

        // Add back the temp line if connecting
        if (this.isConnecting && this.tempLine) {
             // Already handled by SVG innerHTML in drawTempLine, but let's consolidate if needed
        } else {
            this.svg.innerHTML = html;
        }
    }

    runPipeline() {
        if (this.nodes.length === 0) {
            window.showToast("任务流水线", "画布中没有检测到可执行的技能节点！请从左侧拖入技能卡片。", "error");
            return;
        }

        this.isRunning = true;
        window.showToast("任务流水线", "流水线已启动。正在进行拓扑排序并分配执行节点...", "success");

        // Set all nodes to loading status
        this.nodes.forEach(node => {
            this.setNodeStatus(node.el, 'loading', '执行中...');
        });

        // Simulating step-by-step execution feedback
        this.nodes.forEach((node, idx) => {
            setTimeout(() => {
                if (!this.isRunning) return; // Prevent if paused/cleared in between
                this.setNodeStatus(node.el, 'success', '✔ 成功');
                const skillName = node.el.dataset.skillId || '技能';
                window.showToast("执行成功", `步骤 [${skillName}] 已成功完成。`, "success");

                // If it is the last step
                if (idx === this.nodes.length - 1) {
                    this.isRunning = false;
                    window.showToast("流水线执行完成", "所有 DAG 节点已顺利执行完毕，状态已保存。", "success");
                }
            }, (idx + 1) * 1500);
        });
    }

    pausePipeline() {
        this.isRunning = false;
        // Remove status badges
        this.nodes.forEach(node => {
            const badge = node.el.querySelector('.dag-node-status-badge');
            if (badge) badge.remove();
        });
        window.showToast("任务流水线", "流水线已成功暂停。", "warning");
    }

    clearCanvas() {
        this.isRunning = false;
        this.connections = [];
        this.nodes = [];

        // Remove all nodes from DOM except placeholder
        const nodesToClear = this.canvas.querySelectorAll('.dag-node');
        nodesToClear.forEach(node => node.remove());

        this.svg.innerHTML = '';

        // Show placeholder
        const placeholder = this.canvas.querySelector('.canvas-placeholder');
        if (placeholder) placeholder.style.display = 'flex';

        window.showToast("任务流水线", "画布已清空并复位。", "success");
    }

    setNodeStatus(nodeEl, status, text) {
        let badge = nodeEl.querySelector('.dag-node-status-badge');
        if (!badge) {
            badge = document.createElement('div');
            nodeEl.appendChild(badge);
        }
        badge.className = `dag-node-status-badge ${status}`;
        badge.innerText = text;
    }
}

// Global hooks for toolbar
window.runDagPipeline = () => {
    if (window.dagEngine) window.dagEngine.runPipeline();
};

window.pauseDagPipeline = () => {
    if (window.dagEngine) window.dagEngine.pausePipeline();
};

window.clearDagCanvas = () => {
    if (window.dagEngine) window.dagEngine.clearCanvas();
};

document.addEventListener('DOMContentLoaded', () => {
    window.dagEngine = new DAGEngine();
});
