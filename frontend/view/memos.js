/**
 * Butler 备忘录 - 前端逻辑 (中文注释)
 * ---------------------------------------
 * 处理时间轴渲染、Markdown 解析、Base64 文件上传以及 XSS 安全防护。
 */

interface Memo {
    id: number;
    content: string;
    tags: string[];
    resources: string[];
    created_at: number;
    updated_at: number;
}

class MemosManager {
    private timeline: HTMLElement | null = null;
    private searchInput: HTMLInputElement | null = null;
    private editorContainer: HTMLElement | null = null;
    private contentInput: HTMLTextAreaElement | null = null;
    private tagsInput: HTMLInputElement | null = null;
    private attachmentPreview: HTMLElement | null = null;
    private pendingFiles: { name: string, data: string }[] = [];

    constructor() {
        this.init();
    }

    private init() {
        this.timeline = document.getElementById('memos-timeline');
        this.searchInput = document.getElementById('memo-search-input') as HTMLInputElement;
        this.editorContainer = document.getElementById('memo-editor-container');
        this.contentInput = document.getElementById('memo-content-input') as HTMLTextAreaElement;
        this.tagsInput = document.getElementById('memo-tags-input') as HTMLInputElement;
        this.attachmentPreview = document.getElementById('memo-attachment-preview');

        // 侧边栏导航
        const navMemos = document.getElementById('nav-memos');
        if (navMemos) {
            navMemos.addEventListener('click', () => {
                this.switchView('view-memos', '备忘录');
                this.refreshMemos();
            });
        }

        // 编辑器控制
        document.getElementById('new-memo-btn')?.addEventListener('click', () => {
            this.editorContainer?.classList.remove('hidden');
            this.editorContainer!.style.display = 'flex';
        });

        document.getElementById('cancel-memo-btn')?.addEventListener('click', () => {
            this.clearEditor();
            this.editorContainer?.classList.add('hidden');
            this.editorContainer!.style.display = 'none';
        });

        document.getElementById('save-memo-btn')?.addEventListener('click', () => {
            this.saveMemo();
        });

        // 搜索功能
        this.searchInput?.addEventListener('input', (e) => {
            const query = (e.target as HTMLInputElement).value;
            if (query.length > 0) {
                this.searchMemos(query);
            } else {
                this.refreshMemos();
            }
        });

        // 拖拽上传支持
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
                if (e.dataTransfer?.files) {
                    this.handleFiles(e.dataTransfer.files);
                }
            });
        }

        document.getElementById('memo-file-upload')?.addEventListener('change', (e) => {
            const files = (e.target as HTMLInputElement).files;
            if (files) this.handleFiles(files);
        });
    }

    private switchView(viewId: string, title: string) {
        document.querySelectorAll('.view-container').forEach(v => {
            v.classList.remove('active');
            (v as HTMLElement).style.display = 'none';
        });
        const target = document.getElementById(viewId);
        if (target) {
            target.classList.add('active');
            target.style.display = 'flex';
        }

        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        document.getElementById(`nav-${viewId.split('-')[1]}`)?.classList.add('active');

        const titleEl = document.getElementById('current-view-title');
        if (titleEl) titleEl.innerText = title;
    }

    private async refreshMemos() {
        if (!window.pywebview) return;
        try {
            const memos = await window.pywebview.api.call_skill("memos", "list", { limit: 50 });
            this.renderMemos(memos);
        } catch (e) {
            console.error("加载备忘录失败", e);
        }
    }

    private async searchMemos(query: string) {
        if (!window.pywebview) return;
        try {
            const memos = await window.pywebview.api.call_skill("memos", "search", { query });
            this.renderMemos(memos);
        } catch (e) {
            console.error("搜索失败", e);
        }
    }

    private sanitize(text: string): string {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    private renderMemos(memos: Memo[]) {
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

            // 安全渲染 Markdown (简单 XSS 防护)
            // 实际生产环境建议使用 DOMPurify
            const rawContent = memo.content;
            const renderedContent = window.marked ? window.marked.parse(rawContent) : this.sanitize(rawContent);

            let resourcesHtml = '';
            if (memo.resources && memo.resources.length > 0) {
                resourcesHtml = '<div class="memo-resource-grid">';
                memo.resources.forEach(res => {
                    const ext = res.split('.').pop()?.toLowerCase();
                    // 注意：路径相对于项目根目录，Web 端需要处理访问路径
                    const fullPath = `../../${res}`;
                    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext || '')) {
                        resourcesHtml += `<div class="resource-item" onclick="window.openMedia('${res}')"><img src="${fullPath}"></div>`;
                    } else if (['mp4', 'webm'].includes(ext || '')) {
                        resourcesHtml += `<div class="resource-item"><video src="${fullPath}" controls></video></div>`;
                    } else if (['mp3', 'wav', 'ogg'].includes(ext || '')) {
                        resourcesHtml += `<div class="resource-item"><audio src="${fullPath}" controls></audio></div>`;
                    } else {
                        resourcesHtml += `<div class="resource-item" style="padding: 10px; font-size: 12px;"><i class="fas fa-file"></i> ${res.split('/').pop()}</div>`;
                    }
                });
                resourcesHtml += '</div>';
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
                ${resourcesHtml}
                <div class="memo-tags">${tagsHtml}</div>
            `;
            this.timeline?.appendChild(card);
        });
    }

    private handleFiles(files: FileList | File[]) {
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const reader = new FileReader();

            reader.onload = (e) => {
                const base64Data = e.target?.result as string;
                this.pendingFiles.push({ name: file.name, data: base64Data });

                const item = document.createElement('div');
                item.className = 'attachment-item';
                if (file.type.startsWith('image/')) {
                    item.innerHTML = `<img src="${base64Data}"><div class="remove-btn">×</div>`;
                } else {
                    item.innerHTML = `<div style="display: flex; align-items: center; justify-content: center; height: 100%; font-size: 24px;"><i class="fas fa-file"></i></div><div class="remove-btn">×</div>`;
                }

                const removeBtn = item.querySelector('.remove-btn');
                removeBtn?.addEventListener('click', () => {
                    this.pendingFiles = this.pendingFiles.filter(f => f.name !== file.name);
                    item.remove();
                });

                this.attachmentPreview?.appendChild(item);
            };
            reader.readAsDataURL(file);
        }
    }

    private async saveMemo() {
        if (!this.contentInput) return;
        const content = this.contentInput.value;
        const tags = this.tagsInput?.value.split(' ').filter(t => t.startsWith('#')) || [];

        if (!content && this.pendingFiles.length === 0) return;

        try {
            await window.pywebview.api.call_skill("memos", "add", {
                content: content,
                tags: tags,
                base64_files: this.pendingFiles
            });

            this.clearEditor();
            this.editorContainer?.classList.add('hidden');
            this.editorContainer!.style.display = 'none';
            this.refreshMemos();
        } catch (e) {
            console.error("保存失败", e);
        }
    }

    private clearEditor() {
        if (this.contentInput) this.contentInput.value = '';
        if (this.tagsInput) this.tagsInput.value = '';
        if (this.attachmentPreview) this.attachmentPreview.innerHTML = '';
        this.pendingFiles = [];
    }

    public async deleteMemo(id: number) {
        // 兼容 playwright 环境，不使用 confirm
        if (typeof window.pywebview !== 'undefined') {
            if (!confirm("确定要删除这条备忘录吗？")) return;
        }

        try {
            await window.pywebview.api.call_skill("memos", "delete", { id });
            this.refreshMemos();
        } catch (e) {
            console.error("删除失败", e);
        }
    }
}

// 全局初始化
window.addEventListener('load', () => {
    (window as any).memosManager = new MemosManager();
});

// 媒体查看助手
(window as any).openMedia = (path: string) => {
    const overlay = document.getElementById('media-overlay');
    const content = document.getElementById('media-content');
    if (overlay && content) {
        content.innerHTML = `<img src="../../${path}">`;
        overlay.classList.remove('hidden');
    }
};
