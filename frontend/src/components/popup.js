/**
 * Butler 浮动弹出窗口 (Floating Popups)
 *
 * 将活跃的对话线程弹出到独立的窗口中，可以在屏幕上自由移动。
 * 支持置顶状态切换，确保在工作流程中始终可见。
 *
 * 功能：
 * - 拖拽移动
 * - 调整大小
 * - 置顶/取消置顶
 * - 多弹出窗口管理
 * - 最小化/恢复
 * - 窗口间通信
 */

class FloatingPopup {
    constructor(options = {}) {
        this.id = options.id || `popup-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;
        this.title = options.title || 'Butler 弹出窗口';
        this.content = options.content || '';
        this.width = options.width || 420;
        this.height = options.height || 320;
        this.x = options.x || 100;
        this.y = options.y || 100;
        this.isPinned = options.isPinned || false;
        this.isMinimized = false;
        this.isMaximized = false;
        this.zIndex = options.zIndex || 1000;
        this.onClose = options.onClose || null;
        this.onDragStart = options.onDragStart || null;
        this.onDragEnd = options.onDragEnd || null;

        this.element = null;
        this.headerEl = null;
        this.contentEl = null;
        this.resizeHandle = null;
        this._isDragging = false;
        this._dragOffset = { x: 0, y: 0 };

        this._build();
    }

    _build() {
        this.element = document.createElement('div');
        this.element.id = this.id;
        this.element.style.cssText = `
            position: fixed;
            left: ${this.x}px;
            top: ${this.y}px;
            width: ${this.width}px;
            height: ${this.height}px;
            background: rgba(25, 25, 35, 0.97);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 14px;
            box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35),
                        0 0 0 1px rgba(255, 255, 255, 0.04) inset;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            z-index: ${this.zIndex};
            font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
            color: #fff;
            transition: box-shadow 0.2s, transform 0.15s;
        `;

        this.headerEl = document.createElement('div');
        this.headerEl.style.cssText = `
            display: flex;
            align-items: center;
            padding: 10px 14px;
            background: linear-gradient(180deg, rgba(60,60,80,0.9) 0%, rgba(40,40,55,0.9) 100%);
            border-bottom: 1px solid rgba(255,255,255,0.08);
            cursor: grab;
            user-select: none;
            flex-shrink: 0;
        `;

        const dots = document.createElement('div');
        dots.style.cssText = `
            display: flex;
            gap: 6px;
            margin-right: 10px;
        `;
        dots.innerHTML = `
            <div style="width: 10px; height: 10px; border-radius: 50%; background: #ff5f57; cursor: pointer;" data-action="close"></div>
            <div style="width: 10px; height: 10px; border-radius: 50%; background: #febc2e; cursor: pointer;" data-action="minimize"></div>
            <div style="width: 10px; height: 10px; border-radius: 50%; background: #28c840; cursor: pointer;" data-action="maximize"></div>
        `;

        const titleEl = document.createElement('div');
        titleEl.style.cssText = `
            flex: 1;
            font-size: 13px;
            font-weight: 500;
            color: rgba(255,255,255,0.9);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        `;
        titleEl.textContent = this.title;

        const pinBtn = document.createElement('button');
        pinBtn.style.cssText = `
            background: transparent;
            border: none;
            color: ${this.isPinned ? '#FF9500' : 'rgba(255,255,255,0.5)'};
            cursor: pointer;
            padding: 4px 8px;
            font-size: 12px;
            transition: color 0.2s;
        `;
        pinBtn.innerHTML = `<i class="fas fa-thumbtack"></i>`;
        pinBtn.title = this.isPinned ? '取消置顶' : '置顶窗口';
        pinBtn.addEventListener('click', () => this.togglePin());

        this.headerEl.appendChild(dots);
        this.headerEl.appendChild(titleEl);
        this.headerEl.appendChild(pinBtn);

        this.contentEl = document.createElement('div');
        this.contentEl.style.cssText = `
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            font-size: 13px;
            line-height: 1.6;
        `;
        this.contentEl.innerHTML = this.content;

        this.resizeHandle = document.createElement('div');
        this.resizeHandle.style.cssText = `
            position: absolute;
            right: 0;
            bottom: 0;
            width: 14px;
            height: 14px;
            cursor: nwse-resize;
            background: transparent;
        `;
        this.resizeHandle.innerHTML = `
            <svg width="10" height="10" viewBox="0 0 10 10" style="position: absolute; right: 2px; bottom: 2px;">
                <path d="M9 1L1 9M9 5L5 9" stroke="rgba(255,255,255,0.3)" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
        `;

        this.element.appendChild(this.headerEl);
        this.element.appendChild(this.contentEl);
        this.element.appendChild(this.resizeHandle);

        this._bindHeaderEvents(dots);
        this._bindResizeEvents();

        document.body.appendChild(this.element);
    }

    _bindHeaderEvents(dots) {
        dots.querySelectorAll('div[data-action]').forEach(dot => {
            dot.addEventListener('click', (e) => {
                e.stopPropagation();
                const action = dot.dataset.action;
                if (action === 'close') {
                    this.close();
                } else if (action === 'minimize') {
                    this.minimize();
                } else if (action === 'maximize') {
                    this.toggleMaximize();
                }
            });
        });

        this.headerEl.addEventListener('mousedown', (e) => this._startDrag(e));
        document.addEventListener('mousemove', (e) => this._onDrag(e));
        document.addEventListener('mouseup', (e) => this._endDrag(e));

        this.element.addEventListener('mousedown', () => {
            if (!this.isPinned) {
                this._bringToFront();
            }
        });
    }

    _bindResizeEvents() {
        let startX, startY, startWidth, startHeight;

        this.resizeHandle.addEventListener('mousedown', (e) => {
            e.stopPropagation();
            startX = e.clientX;
            startY = e.clientY;
            startWidth = this.element.offsetWidth;
            startHeight = this.element.offsetHeight;
            document.body.style.cursor = 'nwse-resize';
        });

        document.addEventListener('mousemove', (e) => {
            if (startX === undefined) return;
            const newWidth = startWidth + (e.clientX - startX);
            const newHeight = startHeight + (e.clientY - startY);
            this.element.style.width = Math.max(280, newWidth) + 'px';
            this.element.style.height = Math.max(180, newHeight) + 'px';
        });

        document.addEventListener('mouseup', () => {
            if (startX !== undefined) {
                startX = undefined;
                document.body.style.cursor = '';
            }
        });
    }

    _startDrag(e) {
        if (e.target.closest('button') || e.target.closest('[data-action]')) return;
        if (this.isMaximized) return;

        this._isDragging = true;
        const rect = this.element.getBoundingClientRect();
        this._dragOffset.x = e.clientX - rect.left;
        this._dragOffset.y = e.clientY - rect.top;

        if (this.onDragStart) this.onDragStart(this);
    }

    _onDrag(e) {
        if (!this._isDragging) return;

        let newX = e.clientX - this._dragOffset.x;
        let newY = e.clientY - this._dragOffset.y;

        const maxX = window.innerWidth - this.element.offsetWidth;
        const maxY = window.innerHeight - 40;

        newX = Math.max(0, Math.min(newX, maxX));
        newY = Math.max(0, Math.min(newY, maxY));

        this.element.style.left = newX + 'px';
        this.element.style.top = newY + 'px';
    }

    _endDrag(e) {
        if (!this._isDragging) return;
        this._isDragging = false;
        if (this.onDragEnd) this.onDragEnd(this);
    }

    _bringToFront() {
        const maxZ = FloatingPopup._maxZ || 1000;
        this.zIndex = maxZ + 1;
        this.element.style.zIndex = this.zIndex;
        FloatingPopup._maxZ = this.zIndex;
    }

    close() {
        if (this.onClose) this.onClose(this);
        if (this.element) {
            this.element.style.transition = 'opacity 0.2s, transform 0.2s';
            this.element.style.opacity = '0';
            this.element.style.transform = 'scale(0.95)';
            setTimeout(() => {
                if (this.element && this.element.parentNode) {
                    this.element.parentNode.removeChild(this.element);
                }
            }, 200);
        }
        FloatingPopupManager.remove(this.id);
    }

    minimize() {
        if (this.isMinimized) {
            this.element.style.height = this._prevHeight + 'px';
            this.element.style.opacity = '1';
            this.isMinimized = false;
        } else {
            this._prevHeight = this.element.offsetHeight;
            this.element.style.height = '48px';
            this.element.style.opacity = '0.9';
            this.isMinimized = true;
        }
    }

    toggleMaximize() {
        if (this.isMaximized) {
            this.element.style.left = this._prevX + 'px';
            this.element.style.top = this._prevY + 'px';
            this.element.style.width = this._prevWidth + 'px';
            this.element.style.height = this._prevHeight + 'px';
            this.isMaximized = false;
        } else {
            this._prevX = parseInt(this.element.style.left);
            this._prevY = parseInt(this.element.style.top);
            this._prevWidth = this.element.offsetWidth;
            this._prevHeight = this.element.offsetHeight;
            this.element.style.left = '10px';
            this.element.style.top = '10px';
            this.element.style.width = (window.innerWidth - 20) + 'px';
            this.element.style.height = (window.innerHeight - 20) + 'px';
            this.isMaximized = true;
        }
    }

    togglePin() {
        this.isPinned = !this.isPinned;
        const pinBtn = this.headerEl.querySelector('.fa-thumbtack').parentElement;
        const pinIcon = pinBtn.querySelector('.fa-thumbtack');

        if (this.isPinned) {
            pinBtn.style.color = '#FF9500';
            pinBtn.title = '取消置顶';
            this.element.style.boxShadow = '0 24px 64px rgba(0, 0, 0, 0.5), 0 0 0 2px rgba(255, 149, 0, 0.3)';
        } else {
            pinBtn.style.color = 'rgba(255,255,255,0.5)';
            pinBtn.title = '置顶窗口';
            this.element.style.boxShadow = '';
        }
    }

    setContent(html) {
        if (this.contentEl) {
            this.contentEl.innerHTML = html;
        }
    }

    setTitle(title) {
        this.title = title;
        const titleEl = this.headerEl.querySelector('div:nth-child(2)');
        if (titleEl) titleEl.textContent = title;
    }

    getPosition() {
        return {
            x: parseInt(this.element.style.left),
            y: parseInt(this.element.style.top),
            width: this.element.offsetWidth,
            height: this.element.offsetHeight,
        };
    }
}

FloatingPopup._maxZ = 1000;


class FloatingPopupManager {
    static _popups = new Map();

    static create(options = {}) {
        const popup = new FloatingPopup(options);
        FloatingPopupManager._popups.set(popup.id, popup);
        return popup;
    }

    static get(id) {
        return FloatingPopupManager._popups.get(id);
    }

    static remove(id) {
        FloatingPopupManager._popups.delete(id);
    }

    static list() {
        return Array.from(FloatingPopupManager._popups.values());
    }

    static closeAll() {
        FloatingPopupManager._popups.forEach(popup => popup.close());
        FloatingPopupManager._popups.clear();
    }

    static sendToAll(message, data) {
        FloatingPopupManager._popups.forEach(popup => {
            if (popup.onMessage) {
                popup.onMessage(message, data);
            }
        });
    }
}

window.FloatingPopup = FloatingPopup;
window.FloatingPopupManager = FloatingPopupManager;
