/**
 * Butler StateMatrix: Single Source of Truth for high-frequency UI state.
 * Stores metrics, coordinates, drag states, and wormhole thresholds.
 */
class StateMatrix {
    constructor() {
        this.state = {
            // Matrix coordinates (0 to 1)
            matrix: {
                x: 0,
                y: 0,
                targetX: 0,
                targetY: 0,
                isMoving: false
            },
            // System metrics
            metrics: {
                cpu: 0,
                memory: 0,
                disk: 0,
                network: 0
            },
            // Drag and Drop states
            drag: {
                isDragging: false,
                sourceQuadrant: null,
                targetQuadrant: null,
                currentX: 0,
                currentY: 0,
                draggedId: null
            },
            // Wormhole / Gate states
            wormhole: {
                activeGate: null,
                pullStrength: 0
            },
            // Editor states
            editor: {
                active: false,
                filePath: null
            },
            // Time Machine states
            timemachine: {
                active: false
            }
        };

        this.listeners = new Set();
    }

    update(path, value) {
        const parts = path.split('.');
        let current = this.state;
        for (let i = 0; i < parts.length - 1; i++) {
            current = current[parts[i]];
        }
        current[parts[parts.length - 1]] = value;
        this.notify();
    }

    get(path) {
        const parts = path.split('.');
        let current = this.state;
        for (const part of parts) {
            if (current[part] === undefined) return undefined;
            current = current[part];
        }
        return current;
    }

    subscribe(callback) {
        this.listeners.add(callback);
        return () => this.listeners.delete(callback);
    }

    notify() {
        this.listeners.forEach(callback => callback(this.state));
    }
}

// Global singleton instance
window.stateMatrix = new StateMatrix();
