/**
 * Butler 备忘录 - 前端逻辑 (JS)
 */

class MemosManager {
    constructor() {
        this.timeline = null;
        this.searchInput = null;
        this.editorContainer = null;
        this.contentInput = null;
        this.tagsInput = null;
        this.attachmentPreview = null;
        this.pendingFiles = [];
        this.network = null;
        this.currentMemos = [];
        this.viewMode = 'list';
        this.init();
    }

    init() {
        this.timeline = document.getElementById('memos-timeline');
        this.searchInput = document.getElementById('memo-search-input');
        this.editorContainer = document.getElementById('memo-editor-container');
        this.contentInput = document.getElementById('memo-content-input');
        this.tagsInput = document.getElementById('memo-tags-input');
        this.attachmentPreview = document.getElementById('memo-attachment-preview');

        const navMemos = document.getElementById('nav-memos');
        if (navMemos) {
            navMemos.addEventListener('click', () => {
                this.switchView('view-memos', '备忘录');
                this.refreshMemos();
            });
        }

        document.getElementById('new-memo-btn')?.addEventListener('click', () => {
            if (this.editorContainer) {
                this.editorContainer.classList.remove('hidden');
                this.editorContainer.style.display = 'flex';
            }
        });

        document.getElementById('cancel-memo-btn')?.addEventListener('click', () => {
            this.clearEditor();
            if (this.editorContainer) {
                this.editorContainer.classList.add('hidden');
                this.editorContainer.style.display = 'none';
            }
        });

        document.getElementById('save-memo-btn')?.addEventListener('click', () => {
            this.saveMemo();
        });

        document.getElementById('memos-list-view-btn')?.addEventListener('click', () => {
            this.setViewMode('list');
        });
        document.getElementById('memos-spatial-view-btn')?.addEventListener('click', () => {
            this.setViewMode('spatial');
        });

        document.getElementById('close-memo-sidebar')?.addEventListener('click', () => {
            document.getElementById('memo-detail-sidebar')?.classList.add('side-panel-hidden');
        });

        this.searchInput?.addEventListener('input', (e) => {
            const query = e.target.value;
            if (query.length > 0) {
                this.searchMemos(query);
            } else {
                this.refreshMemos();
            }
        });

        const dropZone = document.getElementById('memo-drop-zone');
        if (dropZone) {
            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('active');
            });
            dropZone.addEventListener('dragleave', () => {
                dropZone.classList.remove('active');
            });
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('active');
                if (e.dataTransfer && e.dataTransfer.files) {
                    this.handleFiles(e.dataTransfer.files);
                }
            });
        }

        document.getElementById('memo-file-upload')?.addEventListener('change', (e) => {
            const files = e.target.files;
            if (files) this.handleFiles(files);
        });
    }

    switchView(viewId, title) {
        document.querySelectorAll('.view-container').forEach(v => {
            v.classList.remove('active');
            v.style.display = 'none';
        });
        const target = document.getElementById(viewId);
        if (target) {
            target.classList.add('active');
            target.style.display = 'flex';
        }

        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        const navItem = document.getElementById(`nav-${viewId.split('-')[1]}`);
        if (navItem) navItem.classList.add('active');

        const titleEl = document.getElementById('current-view-title');
        if (titleEl) titleEl.innerText = title;
    }

    async refreshMemos() {
        if (!window.pywebview) return;
        try {
            const memos = await window.pywebview.api.call_skill("memos", "list", { limit: 100 });
            this.currentMemos = memos;
            this.renderCurrentView();
            this.renderHeatmap();
        } catch (e) {
            console.error("加载备忘录失败", e);
        }
    }

    async searchMemos(query) {
        if (!window.pywebview) return;
        try {
            const memos = await window.pywebview.api.call_skill("memos", "search", { query });
            this.currentMemos = memos;
            this.renderCurrentView();
        } catch (e) {
            console.error("搜索失败", e);
        }
    }

    setViewMode(mode) {
        this.viewMode = mode;
        const listBtn = document.getElementById('memos-list-view-btn');
        const spatialBtn = document.getElementById('memos-spatial-view-btn');
        const listWrapper = document.getElementById('memos-list-wrapper');
        const spatialWrapper = document.getElementById('memos-spatial-wrapper');

        if (mode === 'list') {
            listBtn?.classList.add('active');
            spatialBtn?.classList.remove('active');
            listWrapper?.classList.remove('hidden');
            spatialWrapper?.classList.add('hidden');
        } else {
            spatialBtn?.classList.add('active');
            listBtn?.classList.remove('active');
            spatialWrapper?.classList.remove('hidden');
            listWrapper?.classList.add('hidden');
            this.renderSpatialView();
        }
    }

    renderCurrentView() {
        if (this.viewMode === 'list') {
            this.renderMemos(this.currentMemos);
        } else {
            this.renderSpatialView();
        }
    }

    sanitize(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    renderSpatialView() {
        const container = document.getElementById('memos-spatial-container');
        if (!container || !window.vis) return;

        const nodes = new window.vis.DataSet();
        const edges = new window.vis.DataSet();
        const tagMap = {};

        this.currentMemos.forEach(memo => {
            nodes.add({
                id: memo.id,
                label: memo.content.substring(0, 20) + (memo.content.length > 20 ? '...' : ''),
                title: memo.content,
                color: { background: 'rgba(0, 122, 255, 0.2)', border: '#007AFF' },
                font: { color: '#ffffff' },
                shape: 'box',
                margin: 10
            });

            memo.tags.forEach(tag => {
                if (!tagMap[tag]) tagMap[tag] = [];
                tagMap[tag].push(memo.id);
            });
        });

        Object.keys(tagMap).forEach(tag => {
            const ids = tagMap[tag];
            for (let i = 0; i < ids.length; i++) {
                for (let j = i + 1; j < ids.length; j++) {
                    edges.add({
                        from: ids[i],
                        to: ids[j],
                        label: tag,
                        color: { color: 'rgba(255,255,255,0.2)' },
                        font: { size: 10, color: 'rgba(255,255,255,0.4)', strokeWidth: 0 }
                    });
                }
            }
        });

        const data = { nodes, edges };
        const options = {
            physics: { enabled: true, solver: 'forceAtlas2Based' },
            interaction: { hover: true, zoomView: true }
        };

        this.network = new window.vis.Network(container, data, options);
        this.network.on("click", (params) => {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const memo = this.currentMemos.find(m => m.id === nodeId);
                if (memo) this.showMemoDetail(memo);
            }
        });
    }

    showMemoDetail(memo) {
        const sidebar = document.getElementById('memo-detail-sidebar');
        const dateEl = document.getElementById('sidebar-memo-date');
        const contentEl = document.getElementById('sidebar-memo-content-display');
        const tagsEl = document.getElementById('sidebar-memo-tags');
        const resEl = document.getElementById('sidebar-memo-resources');

        if (!sidebar) return;
        sidebar.classList.remove('side-panel-hidden');
        if (dateEl) dateEl.innerText = new Date(memo.created_at * 1000).toLocaleString();
        if (contentEl) contentEl.innerHTML = window.marked ? window.marked.parse(memo.content) : this.sanitize(memo.content);
        if (tagsEl) tagsEl.innerHTML = memo.tags.map(t => `<span class="tag-item">${this.sanitize(t)}</span>`).join('');

        if (resEl) {
            resEl.innerHTML = '';
            memo.resources.forEach(res => {
                const div = document.createElement('div');
                div.className = 'resource-item';
                div.innerHTML = `<div style="font-size: 10px; opacity: 0.6;">${res.split('/').pop()}</div>`;
                resEl.appendChild(div);
            });
        }

        const deleteBtn = document.getElementById('sidebar-delete-btn');
        if (deleteBtn) {
            deleteBtn.onclick = () => this.deleteMemo(memo.id);
        }
    }

    renderHeatmap() {
        const heatmapContainer = document.getElementById('memos-heatmap-container');
        const heatmapBody = document.getElementById('memos-heatmap');
        if (!heatmapBody) return;

        heatmapContainer?.classList.remove('hidden');
        heatmapBody.innerHTML = '';

        const now = new Date();
        const days = 30;
        const counts = {};

        this.currentMemos.forEach(m => {
            const d = new Date(m.created_at * 1000).toDateString();
            counts[d] = (counts[d] || 0) + 1;
        });

        for (let i = days; i >= 0; i--) {
            const d = new Date();
            d.setDate(now.getDate() - i);
            const dateStr = d.toDateString();
            const count = counts[dateStr] || 0;

            const box = document.createElement('div');
            box.className = 'heatmap-box';
            let opacity = 0.1;
            if (count > 0) opacity = 0.3 + (count * 0.2);
            if (opacity > 1) opacity = 1;
            box.style.background = `rgba(0, 122, 255, ${opacity})`;
            box.title = `${d.toLocaleDateString()}: ${count} 条备忘`;
            heatmapBody.appendChild(box);
        }
    }

    renderMemos(memos) {
        if (!this.timeline) return;
        this.timeline.innerHTML = '';
        if (!memos || memos.length === 0) {
            this.timeline.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 40px;">暂无记录</div>';
            return;
        }

        memos.forEach(memo => {
            const card = document.createElement('div');
            card.className = 'memo-card';
            const date = new Date(memo.created_at * 1000).toLocaleString();
            const renderedContent = window.marked ? window.marked.parse(memo.content) : this.sanitize(memo.content);

            let resHtml = '';
            if (memo.resources && memo.resources.length > 0) {
                resHtml = '<div class="memo-resource-grid">';
                memo.resources.forEach(res => {
                    resHtml += `<div class="resource-item" style="padding: 10px; font-size: 12px;"><i class="fas fa-file"></i> ${res.split('/').pop()}</div>`;
                });
                resHtml += '</div>';
            }

            const tagsHtml = memo.tags.map(t => `<span class="tag-item">${this.sanitize(t)}</span>`).join('');

            card.innerHTML = `
                <div class="memo-card-header">
                    <span class="memo-time">${date}</span>
                    <div class="memo-card-actions">
                        <button class="icon-btn-small" onclick="window.memosManager.deleteMemo(${memo.id})"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
                <div class="memo-card-content">${renderedContent}</div>
                ${resHtml}
                <div class="memo-tags">${tagsHtml}</div>
            `;
            this.timeline.appendChild(card);
        });
    }

    handleFiles(files) {
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const reader = new FileReader();
            reader.onload = (e) => {
                const data = e.target.result;
                this.pendingFiles.push({ name: file.name, data: data });
                const item = document.createElement('div');
                item.className = 'attachment-item';
                item.innerHTML = `<div style="display: flex; align-items: center; justify-content: center; height: 100%; font-size: 24px;"><i class="fas fa-file"></i></div><div class="remove-btn">×</div>`;
                item.querySelector('.remove-btn').onclick = () => {
                    this.pendingFiles = this.pendingFiles.filter(f => f.name !== file.name);
                    item.remove();
                };
                this.attachmentPreview?.appendChild(item);
            };
            reader.readAsDataURL(file);
        }
    }

    async saveMemo() {
        if (!this.contentInput) return;
        const content = this.contentInput.value;
        const tags = this.tagsInput?.value.split(' ').filter(t => t.startsWith('#')) || [];
        if (!content && this.pendingFiles.length === 0) return;
        try {
            await window.pywebview.api.call_skill("memos", "add", { content, tags, base64_files: this.pendingFiles });
            this.clearEditor();
            if (this.editorContainer) {
                this.editorContainer.classList.add('hidden');
                this.editorContainer.style.display = 'none';
            }
            this.refreshMemos();
        } catch (e) { console.error(e); }
    }

    clearEditor() {
        if (this.contentInput) this.contentInput.value = '';
        if (this.tagsInput) this.tagsInput.value = '';
        if (this.attachmentPreview) this.attachmentPreview.innerHTML = '';
        this.pendingFiles = [];
    }

    async deleteMemo(id) {
        if (typeof window.pywebview !== 'undefined' && !confirm("确定要删除吗？")) return;
        try {
            await window.pywebview.api.call_skill("memos", "delete", { id });
            this.refreshMemos();
        } catch (e) { console.error(e); }
    }
}

window.addEventListener('load', () => { window.memosManager = new MemosManager(); });
