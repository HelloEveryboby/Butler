/**
 * Butler Memos 备忘录空间 - 前端交互核心 (JS)
 * 高级升级版：支持原地编辑、多模态渲染、AI智能提取、瀑布流画廊、时光网络与 Cyberpunk/Apple 主题融合
 */

class MemosManager {
    constructor() {
        this.timeline = null;
        this.pinnedWrapper = null;
        this.pinnedSection = null;
        this.searchInput = null;
        this.editorContainer = null;
        this.contentInput = null;
        this.tagsInput = null;
        this.attachmentPreview = null;
        this.pendingFiles = [];
        this.network = null;

        // Memos state
        this.currentMemos = [];
        this.pinnedMemos = [];
        this.unpinnedMemos = [];
        this.archivedMemos = [];

        this.viewMode = 'list'; // 'list', 'gallery', 'spatial'
        this.showArchivedOnly = false;
        this.currentEditingMemoId = null; // null for new memo, numeric id for edit
        this.allUniqueTags = [];
        this.aiPredictedTags = [];
        this.tagPredictTimeout = null;

        this.init();

        if (window.marked) {
            window.marked.setOptions({
                headerIds: false,
                mangle: false
            });
        }
    }

    init() {
        // DOM References
        this.timeline = document.getElementById('memos-timeline');
        this.pinnedWrapper = document.getElementById('memos-pinned-wrapper');
        this.pinnedSection = document.getElementById('memos-pinned-section');
        this.searchInput = document.getElementById('memo-search-input');
        this.editorContainer = document.getElementById('memo-editor-container');
        this.contentInput = document.getElementById('memo-content-input');
        this.tagsInput = document.getElementById('memo-tags-input');
        this.attachmentPreview = document.getElementById('memo-attachment-preview');

        // Toolbar Button Events
        document.getElementById('new-memo-btn')?.addEventListener('click', () => {
            this.currentEditingMemoId = null;
            this.clearEditor();
            if (this.editorContainer) {
                this.editorContainer.classList.remove('hidden');
                this.editorContainer.style.display = 'block';
                this.contentInput?.focus();
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

        // View Toggles
        document.getElementById('memos-list-view-btn')?.addEventListener('click', () => {
            this.setViewMode('list');
        });
        document.getElementById('memos-gallery-view-btn')?.addEventListener('click', () => {
            this.setViewMode('gallery');
        });
        document.getElementById('memos-spatial-view-btn')?.addEventListener('click', () => {
            this.setViewMode('spatial');
        });

        // Archive Toggle
        document.getElementById('archive-view-toggle-btn')?.addEventListener('click', (e) => {
            this.showArchivedOnly = !this.showArchivedOnly;
            const btn = e.currentTarget;
            if (this.showArchivedOnly) {
                btn.classList.add('active');
                btn.style.color = '#FF9500';
                btn.style.borderColor = '#FF9500';
                document.getElementById('memos-all-header-title').innerHTML = '<i class="fas fa-archive"></i> <span>已归档备忘录</span>';
                if (this.pinnedSection) this.pinnedSection.classList.add('hidden');
            } else {
                btn.classList.remove('active');
                btn.style.color = '';
                btn.style.borderColor = '';
                document.getElementById('memos-all-header-title').innerHTML = '<i class="fas fa-sticky-note"></i> <span>所有备忘录</span>';
            }
            this.renderCurrentView();
        });

        // Detail Sidebar
        document.getElementById('close-memo-sidebar')?.addEventListener('click', () => {
            document.getElementById('memo-detail-sidebar')?.classList.add('side-panel-hidden');
        });

        // Global Search Input
        this.searchInput?.addEventListener('input', (e) => {
            const query = e.target.value;
            if (query.length > 0) {
                this.searchMemos(query);
            } else {
                this.refreshMemos();
            }
        });

        // Drag & Drop
        const dropZone = document.getElementById('memo-drop-zone');
        if (dropZone) {
            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('active');
                dropZone.style.borderColor = 'var(--accent-color)';
                dropZone.style.background = 'rgba(0, 122, 255, 0.08)';
            });
            dropZone.addEventListener('dragleave', () => {
                dropZone.classList.remove('active');
                dropZone.style.borderColor = '';
                dropZone.style.background = '';
            });
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('active');
                dropZone.style.borderColor = '';
                dropZone.style.background = '';
                if (e.dataTransfer && e.dataTransfer.files) {
                    this.handleFiles(e.dataTransfer.files);
                }
            });
        }

        document.getElementById('memo-file-upload')?.addEventListener('change', (e) => {
            const files = e.target.files;
            if (files) this.handleFiles(files);
        });

        // --- AI Tag Autocomplete & Recommendations ---
        this.tagsInput?.addEventListener('input', (e) => {
            this.handleTagAutocomplete(e);
        });

        this.tagsInput?.addEventListener('keydown', (e) => {
            this.handleTagNavigation(e);
        });

        // AI Tag prediction trigger on content typing
        this.contentInput?.addEventListener('input', () => {
            if (this.currentEditingMemoId) return; // Only suggest for new notes
            clearTimeout(this.tagPredictTimeout);
            this.tagPredictTimeout = setTimeout(() => {
                this.triggerAITagPrediction();
            }, 1200); // 1.2s debounce
        });

        // --- AI Magic Wand Popup ---
        const aiMagicBtn = document.getElementById('memo-ai-magic-btn');
        const aiMagicWandMenu = document.getElementById('ai-magic-wand-menu');

        aiMagicBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            aiMagicWandMenu?.classList.toggle('hidden');
        });

        document.addEventListener('click', () => {
            aiMagicWandMenu?.classList.add('hidden');
        });

        aiMagicWandMenu?.querySelectorAll('.ai-menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const action = e.currentTarget.getAttribute('data-action');
                if (action) {
                    this.triggerAIMagicWand(action);
                }
            });
        });
    }

    async refreshMemos() {
        if (!window.pywebview) return;
        try {
            const memos = await window.pywebview.api.call_skill("memos", "list", { limit: 100 });
            this.currentMemos = memos || [];

            // Rebuild tags pool
            const tagsSet = new Set();
            this.currentMemos.forEach(m => {
                if (m.tags) m.tags.forEach(t => tagsSet.add(t));
            });
            this.allUniqueTags = Array.from(tagsSet);

            // Group memos into pinned, unpinned, and archived
            this.pinnedMemos = this.currentMemos.filter(m => m.is_pinned === 1 && m.is_archived === 0);
            this.unpinnedMemos = this.currentMemos.filter(m => m.is_pinned === 0 && m.is_archived === 0);
            this.archivedMemos = this.currentMemos.filter(m => m.is_archived === 1);

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
            this.currentMemos = memos || [];

            // Filter search results by archive status
            this.pinnedMemos = this.currentMemos.filter(m => m.is_pinned === 1 && m.is_archived === 0);
            this.unpinnedMemos = this.currentMemos.filter(m => m.is_pinned === 0 && m.is_archived === 0);
            this.archivedMemos = this.currentMemos.filter(m => m.is_archived === 1);

            this.renderCurrentView();
        } catch (e) {
            console.error("搜索失败", e);
        }
    }

    setViewMode(mode) {
        this.viewMode = mode;

        const listBtn = document.getElementById('memos-list-view-btn');
        const galleryBtn = document.getElementById('memos-gallery-view-btn');
        const spatialBtn = document.getElementById('memos-spatial-view-btn');

        const listWrapper = document.getElementById('memos-list-wrapper');
        const spatialWrapper = document.getElementById('memos-spatial-wrapper');

        // Reset active states
        [listBtn, galleryBtn, spatialBtn].forEach(btn => btn?.classList.remove('active'));

        if (mode === 'list') {
            listBtn?.classList.add('active');
            listWrapper?.classList.remove('hidden');
            listWrapper?.classList.remove('gallery-grid-layout');
            spatialWrapper?.classList.add('hidden');
            this.renderTimelineView();
        } else if (mode === 'gallery') {
            galleryBtn?.classList.add('active');
            listWrapper?.classList.remove('hidden');
            listWrapper?.classList.add('gallery-grid-layout');
            spatialWrapper?.classList.add('hidden');
            this.renderGalleryView();
        } else {
            spatialBtn?.classList.add('active');
            spatialWrapper?.classList.remove('hidden');
            listWrapper?.classList.add('hidden');
            this.renderSpatialView();
        }
    }

    renderCurrentView() {
        this.setViewMode(this.viewMode);
    }

    sanitize(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    renderTimelineView() {
        // Render Pinned section
        if (this.pinnedMemos.length > 0 && !this.showArchivedOnly) {
            this.pinnedSection?.classList.remove('hidden');
            this.renderMemoCardsList(this.pinnedMemos, this.pinnedWrapper);
        } else {
            this.pinnedSection?.classList.add('hidden');
        }

        // Render standard list section
        const targetList = this.showArchivedOnly ? this.archivedMemos : this.unpinnedMemos;
        this.renderMemoCardsList(targetList, this.timeline);
    }

    renderGalleryView() {
        // In gallery view, we use CSS Column Masonry for multi-column responsive galleries.
        if (this.pinnedMemos.length > 0 && !this.showArchivedOnly) {
            this.pinnedSection?.classList.remove('hidden');
            this.renderMemoCardsList(this.pinnedMemos, this.pinnedWrapper, true);
        } else {
            this.pinnedSection?.classList.add('hidden');
        }

        const targetList = this.showArchivedOnly ? this.archivedMemos : this.unpinnedMemos;
        this.renderMemoCardsList(targetList, this.timeline, true);
    }

    renderMemoCardsList(memos, container, isGallery = false) {
        if (!container) return;
        container.innerHTML = '';

        if (isGallery) {
            container.style.columnCount = memos.length > 1 ? '2' : '1';
            container.style.columnGap = '15px';
        } else {
            container.style.columnCount = '';
            container.style.columnGap = '';
        }

        if (!memos || memos.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 40px; width: 100%;">暂无备忘记录</div>';
            return;
        }

        memos.forEach(memo => {
            const card = document.createElement('div');
            card.className = `memo-card ${memo.is_pinned ? 'pinned-active' : ''}`;
            card.style.breakInside = 'avoid';
            card.style.marginBottom = '15px';

            const date = new Date(memo.created_at * 1000).toLocaleString();
            let renderedContent = window.marked ? window.marked.parse(memo.content) : this.sanitize(memo.content);
            if (window.DOMPurify) {
                renderedContent = window.DOMPurify.sanitize(renderedContent);
            }

            // Extract URLs for Link Bookmarks
            const urlRegex = /(https?:\/\/[^\s]+)/g;
            const urls = memo.content.match(urlRegex);
            let linkCardsHtml = '';
            if (urls && urls.length > 0) {
                urls.forEach(url => {
                    // Only strip trailing punctuation marks like dots, brackets or parentheses
                    const cleanUrl = this.sanitize(url.replace(/[)\].,;!]+$/, ""));
                    linkCardsHtml += `
                        <div class="memo-link-card glass-surface" onclick="window.pywebview ? window.pywebview.api.open_office('${cleanUrl}') : window.open('${cleanUrl}', '_blank')" style="cursor: pointer; padding: 10px; border-radius: 8px; margin-top: 10px; display: flex; align-items: center; gap: 10px; border: 1px solid var(--border-color); background: rgba(255,255,255,0.02);">
                            <i class="fas fa-link" style="color: var(--accent-color); font-size: 14px;"></i>
                            <div style="flex: 1; min-width: 0;">
                                <div style="font-size: 12px; font-weight: 600; color: var(--text-primary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">外部链接书签</div>
                                <div style="font-size: 10px; color: var(--text-secondary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${cleanUrl}</div>
                            </div>
                        </div>
                    `;
                });
            }

            // Multi-modal Previews
            let resHtml = '';
            if (memo.resources && memo.resources.length > 0) {
                resHtml = '<div class="memo-resource-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; margin-top: 12px;">';
                memo.resources.forEach(res => {
                    const filename = res.split('/').pop();
                    const ext = filename.split('.').pop().toLowerCase();
                    const cleanRes = this.sanitize(res);

                    if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) {
                        // Image Thumbnail
                        resHtml += `
                            <div class="resource-item image-preview" onclick="window.memosManager.openLightbox('${cleanRes}')" style="cursor: zoom-in; position: relative; border-radius: 8px; overflow: hidden; height: 90px; border: 1px solid var(--border-color);">
                                <img src="${cleanRes}" style="width: 100%; height: 100%; object-fit: cover;">
                            </div>
                        `;
                    } else if (['mp3', 'wav', 'ogg', 'm4a'].includes(ext)) {
                        // Embedded native audio controller
                        resHtml += `
                            <div class="resource-item audio-preview" style="grid-column: span 2; background: rgba(0,122,255,0.06); padding: 8px; border-radius: 8px; border: 1px solid rgba(0,122,255,0.15);">
                                <div style="font-size: 10px; color: var(--accent-color); margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><i class="fas fa-microphone"></i> 语音附件: ${this.sanitize(filename)}</div>
                                <audio src="${cleanRes}" controls style="width: 100%; height: 28px; outline: none;"></audio>
                            </div>
                        `;
                    } else if (['mp4', 'webm', 'mov'].includes(ext)) {
                        // Embedded native video poster player
                        resHtml += `
                            <div class="resource-item video-preview" style="grid-column: span 2; border-radius: 8px; overflow: hidden; border: 1px solid var(--border-color);">
                                <video src="${cleanRes}" controls poster="" style="width: 100%; max-height: 150px; background: #000; object-fit: contain;"></video>
                            </div>
                        `;
                    } else {
                        // Document file download badge
                        resHtml += `
                            <div class="resource-item doc-badge" onclick="window.pywebview ? window.pywebview.api.open_office('${cleanRes}') : null" style="padding: 10px; font-size: 11px; border-radius: 8px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); display: flex; align-items: center; gap: 8px;">
                                <i class="fas fa-file-alt" style="color: var(--accent-color); font-size: 16px;"></i>
                                <span style="text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${this.sanitize(filename)}</span>
                            </div>
                        `;
                    }
                });
                resHtml += '</div>';
            }

            const tagsHtml = memo.tags.map(t => `<span class="tag-item" style="cursor: pointer;" onclick="window.memosManager.filterByTag('${this.sanitize(t)}')">${this.sanitize(t)}</span>`).join('');

            card.innerHTML = `
                <div class="memo-card-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <span class="memo-time" style="font-size: 11px; color: var(--text-secondary); font-family: monospace;">${this.sanitize(date)}</span>
                    <div class="memo-card-actions" style="display: flex; gap: 4px;">
                        <button class="icon-btn-small" onclick="window.memosManager.editMemoInPlace(${memo.id})" title="编辑备忘"><i class="fas fa-edit"></i></button>
                        <button class="icon-btn-small" onclick="window.memosManager.togglePinStatus(${memo.id}, ${memo.is_pinned})" title="${memo.is_pinned ? '取消置顶' : '置顶备忘'}" style="color: ${memo.is_pinned ? 'var(--accent-color)' : ''};"><i class="fas fa-thumbtack" style="${memo.is_pinned ? 'transform: rotate(45deg);' : ''}"></i></button>
                        <button class="icon-btn-small" onclick="window.memosManager.toggleArchiveStatus(${memo.id}, ${memo.is_archived})" title="${memo.is_archived ? '激活' : '归档备忘'}" style="color: ${memo.is_archived ? '#FF9500' : ''};"><i class="fas fa-archive"></i></button>
                        <button class="icon-btn-small" onclick="window.memosManager.deleteMemo(${memo.id})" title="彻底删除" style="color: #FF3B30;"><i class="fas fa-trash-alt"></i></button>
                    </div>
                </div>
                <div class="memo-card-content" onclick="window.memosManager.showMemoDetail(${JSON.stringify(memo).replace(/"/g, '&quot;')})" style="cursor: pointer;">${renderedContent}</div>
                ${linkCardsHtml}
                ${resHtml}
                <div class="memo-tags" style="margin-top: 10px; display: flex; flex-wrap: wrap; gap: 5px;">${tagsHtml}</div>
            `;
            container.appendChild(card);
        });
    }

    renderSpatialView() {
        const container = document.getElementById('memos-spatial-container');
        if (!container || !window.vis) return;

        const nodes = new window.vis.DataSet();
        const edges = new window.vis.DataSet();
        const tagMap = {};

        // Only display active (non-archived) memos in graph
        const activeMemos = this.currentMemos.filter(m => m.is_archived === 0);

        activeMemos.forEach(memo => {
            nodes.add({
                id: memo.id,
                label: memo.content.substring(0, 20) + (memo.content.length > 20 ? '...' : ''),
                title: memo.content,
                color: { background: 'rgba(0, 122, 255, 0.2)', border: '#007AFF' },
                font: { color: '#ffffff' },
                shape: 'box',
                margin: 10
            });

            if (memo.tags) {
                memo.tags.forEach(tag => {
                    if (!tagMap[tag]) tagMap[tag] = [];
                    tagMap[tag].push(memo.id);
                });
            }
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
        if (typeof memo === 'string') {
            memo = JSON.parse(memo);
        }
        const sidebar = document.getElementById('memo-detail-sidebar');
        const dateEl = document.getElementById('sidebar-memo-date');
        const contentEl = document.getElementById('sidebar-memo-content-display');
        const tagsEl = document.getElementById('sidebar-memo-tags');
        const resEl = document.getElementById('sidebar-memo-resources');

        if (!sidebar) return;
        sidebar.classList.remove('side-panel-hidden');
        if (dateEl) dateEl.innerText = "创建时间：" + new Date(memo.created_at * 1000).toLocaleString();

        // Safe Markdown
        if (contentEl) {
            let html = window.marked ? window.marked.parse(memo.content) : this.sanitize(memo.content);
            if (window.DOMPurify) {
                html = window.DOMPurify.sanitize(html);
            }
            contentEl.innerHTML = html;
        }

        if (tagsEl) {
            tagsEl.innerHTML = (memo.tags || []).map(t => `<span class="tag-item" style="cursor:pointer;" onclick="window.memosManager.filterByTag('${this.sanitize(t)}')">${this.sanitize(t)}</span>`).join('');
        }

        if (resEl) {
            resEl.innerHTML = '';
            if (memo.resources && memo.resources.length > 0) {
                memo.resources.forEach(res => {
                    const div = document.createElement('div');
                    div.className = 'resource-item';
                    const filename = res.split('/').pop();
                    div.innerHTML = `
                        <div class="glass-surface" onclick="window.memosManager.openLightbox('${this.sanitize(res)}')" style="cursor:pointer; padding:6px; border-radius: 6px; font-size: 10px; display:flex; align-items:center; gap:6px; border:1px solid var(--border-color);">
                            <i class="fas fa-file"></i>
                            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:80px;">${this.sanitize(filename)}</span>
                        </div>
                    `;
                    resEl.appendChild(div);
                });
            } else {
                resEl.innerHTML = '<span style="font-size:12px; color:var(--text-secondary);">无附件</span>';
            }
        }

        // Action Hookups
        const deleteBtn = document.getElementById('sidebar-delete-btn');
        if (deleteBtn) {
            deleteBtn.onclick = () => {
                this.deleteMemo(memo.id);
                sidebar.classList.add('side-panel-hidden');
            };
        }

        const pinBtn = document.getElementById('sidebar-pin-btn');
        if (pinBtn) {
            pinBtn.innerHTML = memo.is_pinned ? '<i class="fas fa-thumbtack" style="transform: rotate(45deg);"></i> 取消置顶' : '<i class="fas fa-thumbtack"></i> 置顶备忘';
            pinBtn.onclick = () => {
                this.togglePinStatus(memo.id, memo.is_pinned);
                sidebar.classList.add('side-panel-hidden');
            };
        }

        const archiveBtn = document.getElementById('sidebar-archive-btn');
        if (archiveBtn) {
            archiveBtn.innerHTML = memo.is_archived ? '<i class="fas fa-archive"></i> 恢复至收件箱' : '<i class="fas fa-archive"></i> 归档备忘录';
            archiveBtn.onclick = () => {
                this.toggleArchiveStatus(memo.id, memo.is_archived);
                sidebar.classList.add('side-panel-hidden');
            };
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

        // Show total count indicator
        const indicator = document.getElementById('heatmap-count-indicator');
        if (indicator) {
            indicator.innerText = `当前系统已捕获 ${this.currentMemos.length} 条记录`;
        }

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
            box.title = `${d.toLocaleDateString()}: ${count} 条备忘记录`;

            box.onclick = () => {
                // Clicking heatmap filters list to that day
                const filterDate = d.toLocaleDateString();
                this.searchInput.value = filterDate;
                this.searchMemos(filterDate);
            };

            heatmapBody.appendChild(box);
        }
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
                item.style.position = 'relative';

                const ext = file.name.split('.').pop().toLowerCase();
                if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) {
                    item.innerHTML = `<img src="${data}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px;"><div class="remove-btn" style="position: absolute; top: 2px; right: 2px; width: 18px; height: 18px; background: rgba(0,0,0,0.5); color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; cursor: pointer;">×</div>`;
                } else {
                    item.innerHTML = `<div style="display: flex; align-items: center; justify-content: center; height: 100%; font-size: 24px; background: rgba(255,255,255,0.05); border-radius: 8px;"><i class="fas fa-file-alt"></i></div><div style="font-size: 8px; position: absolute; bottom: 4px; left: 4px; right: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${file.name}</div><div class="remove-btn" style="position: absolute; top: 2px; right: 2px; width: 18px; height: 18px; background: rgba(0,0,0,0.5); color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; cursor: pointer;">×</div>`;
                }

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
        const content = this.contentInput.value.trim();
        const tags = this.tagsInput?.value.split(' ').filter(t => t.startsWith('#')) || [];

        if (!content && this.pendingFiles.length === 0) return;

        try {
            if (this.currentEditingMemoId) {
                // Editing existing memo
                await window.pywebview.api.call_skill("memos", "update", {
                    id: this.currentEditingMemoId,
                    content: content,
                    tags: tags,
                    base64_files: this.pendingFiles
                });
                window.showToast("更新备忘", "备忘录修缮成功！", "success");
            } else {
                // Creating new memo
                await window.pywebview.api.call_skill("memos", "add", {
                    content: content,
                    tags: tags,
                    base64_files: this.pendingFiles
                });
                window.showToast("保存备忘", "新灵感已存入备忘脑库中。", "success");
            }

            this.clearEditor();
            if (this.editorContainer) {
                this.editorContainer.classList.add('hidden');
                this.editorContainer.style.display = 'none';
            }
            this.refreshMemos();
        } catch (e) {
            console.error(e);
            window.showToast("保存失败", "后端服务交互异常：" + e.message, "error");
        }
    }

    editMemoInPlace(id) {
        const memo = this.currentMemos.find(m => m.id === id);
        if (!memo) return;

        this.currentEditingMemoId = memo.id;

        if (this.contentInput) this.contentInput.value = memo.content;
        if (this.tagsInput) this.tagsInput.value = (memo.tags || []).join(' ');

        if (this.attachmentPreview) {
            this.attachmentPreview.innerHTML = '';
            this.pendingFiles = [];

            // Populate existing files as static previews
            (memo.resources || []).forEach(res => {
                const filename = res.split('/').pop();
                const item = document.createElement('div');
                item.className = 'attachment-item';
                item.style.position = 'relative';

                const ext = filename.split('.').pop().toLowerCase();
                if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) {
                    item.innerHTML = `<img src="${res}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px;">`;
                } else {
                    item.innerHTML = `<div style="display: flex; align-items: center; justify-content: center; height: 100%; font-size: 24px; background: rgba(255,255,255,0.05); border-radius: 8px;"><i class="fas fa-file-alt"></i></div><div style="font-size: 8px; position: absolute; bottom: 4px; left: 4px; right: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${filename}</div>`;
                }
                this.attachmentPreview.appendChild(item);
            });
        }

        if (this.editorContainer) {
            this.editorContainer.classList.remove('hidden');
            this.editorContainer.style.display = 'block';
            this.contentInput?.focus();

            // Scroll to editor
            this.editorContainer.scrollIntoView({ behavior: 'smooth' });
        }
    }

    async togglePinStatus(id, currentPinned) {
        if (!window.pywebview) return;
        const newPinned = currentPinned === 1 ? 0 : 1;
        try {
            await window.pywebview.api.call_skill("memos", "update", {
                id: id,
                is_pinned: newPinned
            });
            window.showToast("置顶更新", newPinned === 1 ? "备忘卡片已置顶" : "已取消置顶", "success");
            this.refreshMemos();
        } catch (e) {
            console.error("Failed to pin memo", e);
        }
    }

    async toggleArchiveStatus(id, currentArchived) {
        if (!window.pywebview) return;
        const newArchived = currentArchived === 1 ? 0 : 1;
        try {
            await window.pywebview.api.call_skill("memos", "update", {
                id: id,
                is_archived: newArchived
            });
            window.showToast("归档更新", newArchived === 1 ? "备忘录已归档隐藏" : "已恢复至主时间线", "success");
            this.refreshMemos();
        } catch (e) {
            console.error("Failed to archive memo", e);
        }
    }

    filterByTag(tag) {
        if (this.searchInput) {
            this.searchInput.value = tag;
            this.searchMemos(tag);
        }
    }

    clearEditor() {
        if (this.contentInput) this.contentInput.value = '';
        if (this.tagsInput) this.tagsInput.value = '';
        if (this.attachmentPreview) this.attachmentPreview.innerHTML = '';
        this.pendingFiles = [];
        this.currentEditingMemoId = null;

        // Hide AI Recommendations
        document.getElementById('ai-tag-suggestion-bar')?.classList.add('hidden');
        document.getElementById('ai-suggested-tags-container').innerHTML = '';
    }

    async deleteMemo(id) {
        if (typeof window.pywebview !== 'undefined' && !confirm("确定要永久删除此备忘录吗？此操作不可撤销。")) return;
        try {
            await window.pywebview.api.call_skill("memos", "delete", { id });
            window.showToast("备忘删除", "备忘录已安全清除。", "success");
            this.refreshMemos();
        } catch (e) {
            console.error(e);
        }
    }

    // --- AI Feature Implementations ---

    async triggerAITagPrediction() {
        const text = this.contentInput?.value.trim();
        if (!text || text.length < 15 || text.includes('#')) {
            document.getElementById('ai-tag-suggestion-bar')?.classList.add('hidden');
            return;
        }

        try {
            const predicted = await window.pywebview.api.call_skill("memos", "ai_tag_predict", { content: text });
            if (predicted && predicted.length > 0) {
                const container = document.getElementById('ai-suggested-tags-container');
                const bar = document.getElementById('ai-tag-suggestion-bar');
                if (container && bar) {
                    container.innerHTML = '';
                    predicted.forEach(tag => {
                        const chip = document.createElement('span');
                        chip.className = 'suggestion-chip';
                        chip.style.cssText = "font-size: 11px; background: rgba(88,86,214,0.15); color: #5856D6; padding: 2px 8px; border-radius: 6px; cursor: pointer; font-weight: 500;";
                        chip.innerText = `+ ${tag}`;
                        chip.onclick = () => {
                            this.adoptSuggestedTag(tag);
                            chip.remove();
                            if (container.children.length === 0) {
                                bar.classList.add('hidden');
                            }
                        };
                        container.appendChild(chip);
                    });
                    bar.classList.remove('hidden');
                }
            }
        } catch (e) {
            console.error("AI Tag prediction error", e);
        }
    }

    adoptSuggestedTag(tag) {
        if (this.tagsInput) {
            const current = this.tagsInput.value.trim();
            this.tagsInput.value = current ? `${current} ${tag}` : tag;
        }
    }

    async triggerAIMagicWand(action) {
        const text = this.contentInput?.value.trim();
        if (!text) {
            window.showToast("AI 魔棒", "编辑区内无文本内容可供 AI 解析！", "error");
            return;
        }

        window.showToast("AI 解析中", "AI 魔法总线正在进行深度分析与重新编排...", "success");

        // Disable text area temporarily
        if (this.contentInput) this.contentInput.disabled = true;

        try {
            const processedText = await window.pywebview.api.call_skill("memos", "ai_magic_wand", {
                content: text,
                mode: action
            });

            if (processedText && !processedText.startsWith("Error:") && !processedText.startsWith("AI 处理失败:")) {
                if (this.contentInput) {
                    this.contentInput.value = processedText;
                }
                window.showToast("魔法奏效", "重新编排排版已成功渲染并覆写！", "success");
            } else {
                window.showToast("魔法失败", processedText || "AI 没有返回有效响应", "error");
            }
        } catch (e) {
            console.error(e);
            window.showToast("AI 魔法失败", e.message, "error");
        } finally {
            if (this.contentInput) this.contentInput.disabled = false;
        }
    }

    // Tag Auto-Complete List dropdown listeners
    handleTagAutocomplete(e) {
        const input = e.target;
        const val = input.value;
        const lastWord = val.split(/\s+/).pop();
        const dropdown = document.getElementById('tag-autocomplete-list');

        if (!dropdown) return;

        if (lastWord && lastWord.startsWith('#') && lastWord.length > 1) {
            const prefix = lastWord.toLowerCase();
            const matches = this.allUniqueTags.filter(t => t.toLowerCase().includes(prefix) && t.toLowerCase() !== prefix);

            if (matches.length > 0) {
                dropdown.innerHTML = '';
                matches.forEach((tag, idx) => {
                    const item = document.createElement('div');
                    item.className = `autocomplete-item ${idx === 0 ? 'selected' : ''}`;
                    item.style.cssText = "padding: 6px 12px; font-size: 13px; color: var(--text-primary); cursor: pointer;";
                    item.innerText = tag;
                    item.onclick = () => {
                        this.selectAutocompleteTag(tag);
                    };
                    dropdown.appendChild(item);
                });

                dropdown.classList.remove('hidden');
                dropdown.style.display = 'block';
                return;
            }
        }
        dropdown.classList.add('hidden');
        dropdown.style.display = 'none';
    }

    handleTagNavigation(e) {
        const dropdown = document.getElementById('tag-autocomplete-list');
        if (!dropdown || dropdown.classList.contains('hidden')) return;

        const items = dropdown.querySelectorAll('.autocomplete-item');
        let selectedIdx = Array.from(items).findIndex(item => item.classList.contains('selected'));

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (items[selectedIdx]) items[selectedIdx].classList.remove('selected');
            selectedIdx = (selectedIdx + 1) % items.length;
            if (items[selectedIdx]) items[selectedIdx].classList.add('selected');
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (items[selectedIdx]) items[selectedIdx].classList.remove('selected');
            selectedIdx = (selectedIdx - 1 + items.length) % items.length;
            if (items[selectedIdx]) items[selectedIdx].classList.add('selected');
        } else if (e.key === 'Enter' || e.key === 'Tab') {
            e.preventDefault();
            if (items[selectedIdx]) {
                this.selectAutocompleteTag(items[selectedIdx].innerText);
            }
        }
    }

    selectAutocompleteTag(tag) {
        if (!this.tagsInput) return;
        const words = this.tagsInput.value.split(/\s+/);
        words.pop(); // Remove partial tag
        words.push(tag);
        this.tagsInput.value = words.join(' ') + ' ';
        this.tagsInput.focus();

        const dropdown = document.getElementById('tag-autocomplete-list');
        if (dropdown) {
            dropdown.classList.add('hidden');
            dropdown.style.display = 'none';
        }
    }

    // Lightbox modal view for images
    openLightbox(src) {
        const lightbox = document.createElement('div');
        lightbox.style.cssText = "position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.9); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); z-index: 10000; display: flex; align-items: center; justify-content: center; cursor: zoom-out;";

        const img = document.createElement('img');
        img.src = src;
        img.style.cssText = "max-width: 90%; max-height: 85vh; border-radius: 12px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); object-fit: contain; animation: scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);";

        lightbox.appendChild(img);
        lightbox.onclick = () => {
            lightbox.remove();
        };
        document.body.appendChild(lightbox);
    }
}

if (document.readyState === 'complete' || document.readyState === 'interactive') {
    window.memosManager = new MemosManager();
} else {
    window.addEventListener('DOMContentLoaded', () => {
        window.memosManager = new MemosManager();
    });
}
