/**
 * Butler Memos Manager Component in TypeScript
 */

interface MemoData {
  id: number;
  content: string;
  tags?: string[];
  resources?: string[];
  created_at: number;
  is_pinned?: number;
  is_archived?: number;
}

class MemosManager {
  public timeline: HTMLElement | null = null;
  public pinnedWrapper: HTMLElement | null = null;
  public pinnedSection: HTMLElement | null = null;
  public searchInput: HTMLInputElement | null = null;
  public editorContainer: HTMLElement | null = null;
  public contentInput: HTMLTextAreaElement | null = null;
  public tagsInput: HTMLInputElement | null = null;
  public attachmentPreview: HTMLElement | null = null;
  public pendingFiles: Array<{ name: string; data: string }> = [];
  public network: any = null;

  public currentMemos: MemoData[] = [];
  public pinnedMemos: MemoData[] = [];
  public unpinnedMemos: MemoData[] = [];
  public archivedMemos: MemoData[] = [];

  public viewMode: 'list' | 'gallery' | 'spatial' = 'list';
  public showArchivedOnly: boolean = false;
  public currentEditingMemoId: number | null = null;
  public allUniqueTags: string[] = [];
  public aiPredictedTags: string[] = [];
  public tagPredictTimeout: any = null;

  public selectionMode: boolean = false;
  public selectedIds: Set<number> = new Set();
  public expandedIds: Set<number> = new Set();

  constructor() {
    this.init();

    if (window.marked && window.marked.setOptions) {
      window.marked.setOptions({
        headerIds: false,
        mangle: false,
      });
    }
  }

  public init(): void {
    this.timeline = document.getElementById('memos-timeline');
    this.pinnedWrapper = document.getElementById('memos-pinned-wrapper');
    this.pinnedSection = document.getElementById('memos-pinned-section');
    this.searchInput = document.getElementById('memo-search-input') as HTMLInputElement;
    this.editorContainer = document.getElementById('memo-editor-container');
    this.contentInput = document.getElementById('memo-content-input') as HTMLTextAreaElement;
    this.tagsInput = document.getElementById('memo-tags-input') as HTMLInputElement;
    this.attachmentPreview = document.getElementById('memo-attachment-preview');

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

    document.getElementById('memos-list-view-btn')?.addEventListener('click', () => {
      this.setViewMode('list');
    });
    document.getElementById('memos-gallery-view-btn')?.addEventListener('click', () => {
      this.setViewMode('gallery');
    });
    document.getElementById('memos-spatial-view-btn')?.addEventListener('click', () => {
      this.setViewMode('spatial');
    });

    document.getElementById('archive-view-toggle-btn')?.addEventListener('click', (e: Event) => {
      this.showArchivedOnly = !this.showArchivedOnly;
      const btn = e.currentTarget as HTMLElement;
      const headerTitle = document.getElementById('memos-all-header-title');
      if (this.showArchivedOnly) {
        btn?.classList.add('active');
        if (btn) {
          btn.style.color = '#FF9500';
          btn.style.borderColor = '#FF9500';
        }
        if (headerTitle) {
          headerTitle.innerHTML = '<i class="fas fa-archive"></i> <span>已归档备忘录</span>';
        }
        if (this.pinnedSection) this.pinnedSection.classList.add('hidden');
      } else {
        btn?.classList.remove('active');
        if (btn) {
          btn.style.color = '';
          btn.style.borderColor = '';
        }
        if (headerTitle) {
          headerTitle.innerHTML = '<i class="fas fa-sticky-note"></i> <span>所有备忘录</span>';
        }
      }
      this.renderCurrentView();
    });

    document.getElementById('close-memo-sidebar')?.addEventListener('click', () => {
      document.getElementById('memo-detail-sidebar')?.classList.add('side-panel-hidden');
    });

    this.searchInput?.addEventListener('input', (e: Event) => {
      const query = (e.target as HTMLInputElement).value;
      if (query.length > 0) {
        this.searchMemos(query);
      } else {
        this.refreshMemos();
      }
    });

    document.addEventListener('click', (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const card = target.closest('.memo-card');
      if (!card) return;
      if (
        target.closest('.memo-card-actions') ||
        target.closest('.btn-expand-toggle') ||
        target.closest('.badge') ||
        target.closest('.editable-value') ||
        target.closest('.tag-item') ||
        target.closest('.memo-tags') ||
        target.closest('.memo-resource-grid') ||
        target.closest('.card-checkbox')
      )
        return;
      const toggleBtn = card.querySelector('.btn-expand-toggle') as HTMLElement;
      if (toggleBtn) this.toggleExpand(toggleBtn);
    });

    const dropZone = document.getElementById('memo-drop-zone');
    if (dropZone) {
      dropZone.addEventListener('dragover', (e: DragEvent) => {
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
      dropZone.addEventListener('drop', (e: DragEvent) => {
        e.preventDefault();
        dropZone.classList.remove('active');
        dropZone.style.borderColor = '';
        dropZone.style.background = '';
        if (e.dataTransfer && e.dataTransfer.files) {
          this.handleFiles(e.dataTransfer.files);
        }
      });
    }

    const fileUpload = document.getElementById('memo-file-upload') as HTMLInputElement;
    fileUpload?.addEventListener('change', (e: Event) => {
      const files = (e.target as HTMLInputElement).files;
      if (files) this.handleFiles(files);
    });

    this.tagsInput?.addEventListener('input', (e: Event) => {
      this.handleTagAutocomplete(e);
    });

    this.tagsInput?.addEventListener('keydown', (e: KeyboardEvent) => {
      this.handleTagNavigation(e);
    });

    this.contentInput?.addEventListener('input', () => {
      if (this.currentEditingMemoId) return;
      clearTimeout(this.tagPredictTimeout);
      this.tagPredictTimeout = setTimeout(() => {
        this.triggerAITagPrediction();
      }, 1200);
    });

    const aiMagicBtn = document.getElementById('memo-ai-magic-btn');
    const aiMagicWandMenu = document.getElementById('ai-magic-wand-menu');

    aiMagicBtn?.addEventListener('click', (e: MouseEvent) => {
      e.stopPropagation();
      aiMagicWandMenu?.classList.toggle('hidden');
    });

    document.addEventListener('click', () => {
      aiMagicWandMenu?.classList.add('hidden');
    });

    aiMagicWandMenu?.querySelectorAll('.ai-menu-item').forEach((item) => {
      item.addEventListener('click', (e: Event) => {
        const action = (e.currentTarget as HTMLElement).getAttribute('data-action');
        if (action) {
          this.triggerAIMagicWand(action);
        }
      });
    });
  }

  public async refreshMemos(): Promise<void> {
    if (!window.pywebview) return;
    try {
      const memos: MemoData[] = await window.pywebview.api.call_skill('memos', 'list', { limit: 100 });
      this.currentMemos = memos || [];

      const tagsSet = new Set<string>();
      this.currentMemos.forEach((m) => {
        if (m.tags) m.tags.forEach((t) => tagsSet.add(t));
      });
      this.allUniqueTags = Array.from(tagsSet);

      this.pinnedMemos = this.currentMemos.filter((m) => m.is_pinned === 1 && m.is_archived === 0);
      this.unpinnedMemos = this.currentMemos.filter((m) => m.is_pinned === 0 && m.is_archived === 0);
      this.archivedMemos = this.currentMemos.filter((m) => m.is_archived === 1);

      this.renderCurrentView();
      this.renderHeatmap();
    } catch (e) {
      console.error('加载备忘录失败', e);
    }
  }

  public async searchMemos(query: string): Promise<void> {
    if (!window.pywebview) return;
    try {
      const memos: MemoData[] = await window.pywebview.api.call_skill('memos', 'search', { query });
      this.currentMemos = memos || [];

      this.pinnedMemos = this.currentMemos.filter((m) => m.is_pinned === 1 && m.is_archived === 0);
      this.unpinnedMemos = this.currentMemos.filter((m) => m.is_pinned === 0 && m.is_archived === 0);
      this.archivedMemos = this.currentMemos.filter((m) => m.is_archived === 1);

      this.renderCurrentView();
    } catch (e) {
      console.error('搜索失败', e);
    }
  }

  public setViewMode(mode: 'list' | 'gallery' | 'spatial'): void {
    this.viewMode = mode;

    const listBtn = document.getElementById('memos-list-view-btn');
    const galleryBtn = document.getElementById('memos-gallery-view-btn');
    const spatialBtn = document.getElementById('memos-spatial-view-btn');

    const listWrapper = document.getElementById('memos-list-wrapper');
    const spatialWrapper = document.getElementById('memos-spatial-wrapper');

    [listBtn, galleryBtn, spatialBtn].forEach((btn) => btn?.classList.remove('active'));

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

  public renderCurrentView(): void {
    this.setViewMode(this.viewMode);
  }

  public sanitize(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  public renderTimelineView(): void {
    if (this.pinnedMemos.length > 0 && !this.showArchivedOnly) {
      this.pinnedSection?.classList.remove('hidden');
      this.renderMemoCardsList(this.pinnedMemos, this.pinnedWrapper);
    } else {
      this.pinnedSection?.classList.add('hidden');
    }

    const targetList = this.showArchivedOnly ? this.archivedMemos : this.unpinnedMemos;
    this.renderMemoCardsList(targetList, this.timeline);
  }

  public renderGalleryView(): void {
    if (this.pinnedMemos.length > 0 && !this.showArchivedOnly) {
      this.pinnedSection?.classList.remove('hidden');
      this.renderMemoCardsList(this.pinnedMemos, this.pinnedWrapper, true);
    } else {
      this.pinnedSection?.classList.add('hidden');
    }

    const targetList = this.showArchivedOnly ? this.archivedMemos : this.unpinnedMemos;
    this.renderMemoCardsList(targetList, this.timeline, true);
  }

  public renderMemoCardsList(memos: MemoData[], container: HTMLElement | null, isGallery: boolean = false): void {
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
      container.innerHTML =
        '<div style="text-align: center; color: var(--text-secondary); padding: 40px; width: 100%;">暂无备忘记录</div>';
      return;
    }

    if (memos.length > 0 && this.expandedIds.size === 0) {
      this.expandedIds.add(memos[0].id);
    }

    memos.forEach((memo) => {
      const card = document.createElement('div');
      card.className = `memo-card ${memo.is_pinned ? 'pinned-active' : ''}`;
      card.dataset.note = `${memo.id}`;
      card.style.breakInside = 'avoid';
      card.style.marginBottom = '15px';

      const date = new Date(memo.created_at * 1000).toLocaleString();
      let renderedContent = window.marked ? window.marked.parse(memo.content) : this.sanitize(memo.content);
      if (window.DOMPurify) {
        renderedContent = window.DOMPurify.sanitize(renderedContent);
      }

      const urlRegex = /(https?:\/\/[^\s]+)/g;
      const urls = memo.content.match(urlRegex);
      let linkCardsHtml = '';
      if (urls && urls.length > 0) {
        urls.forEach((url) => {
          const cleanUrl = this.sanitize(url.replace(/[)\].,;!]+$/, ''));
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

      const contentLines = memo.content
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.length > 0);
      let title = '';
      let preview = '';
      if (contentLines.length > 0) {
        title = contentLines[0].replace(/^[#\s\-*]+/g, '');
      }
      if (title.length === 0) {
        title = `📝 备忘记录 #${memo.id}`;
      } else if (title.length > 30) {
        title = title.substring(0, 30) + '...';
      }

      if (contentLines.length > 1) {
        preview = contentLines.slice(1).join(' ');
      } else {
        preview = '点击「详情」查看完整内容...';
      }
      if (preview.length > 80) {
        preview = preview.substring(0, 80) + '...';
      }

      const statusTags = ['#进行中', '#未完成', '#已完成', '#待办', '#新建', '#待做'];
      let status = '进行中';
      if (memo.tags) {
        const foundStatus = memo.tags.find((t) => statusTags.includes(t));
        if (foundStatus) {
          status = foundStatus.substring(1);
        }
      }

      const displayTags = (memo.tags || []).filter((t) => !statusTags.includes(t));
      const primaryTag = displayTags.length > 0 ? displayTags[0].replace(/^#/g, '') : '备忘';

      let detailsHtml = '';
      detailsHtml += `<p><i class="fas fa-check-circle"></i> 状态：<span class="badge" onclick="window.memosManager.editDetail(this, ${memo.id}, '状态')">${this.sanitize(
        status
      )}</span></p>`;
      detailsHtml += `<p><i class="fas fa-tag"></i> 标签：<span class="editable-value" onclick="window.memosManager.editDetail(this, ${memo.id}, '标签')">${this.sanitize(
        (memo.tags || []).join(' ') || '未分类'
      )}</span></p>`;
      detailsHtml += `<p><i class="fas fa-align-left"></i> 详细内容：<span class="editable-value" onclick="window.memosManager.editDetail(this, ${memo.id}, '详细内容')">${renderedContent}</span></p>`;

      let imagesHtml = '';
      const imageResources: string[] = [];
      const nonImageResources: string[] = [];
      if (memo.resources && memo.resources.length > 0) {
        memo.resources.forEach((res) => {
          const filename = res.split('/').pop() || '';
          const ext = filename.split('.').pop()?.toLowerCase() || '';
          if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) {
            imageResources.push(res);
          } else {
            nonImageResources.push(res);
          }
        });
      }

      if (imageResources.length > 0) {
        imagesHtml = `<div class="image-gallery">`;
        imageResources.forEach((img, idx) => {
          imagesHtml += `<img src="${this.sanitize(img)}" alt="图片${idx + 1}" onclick="window.memosManager.openLightbox('${this.sanitize(img)}')" />`;
        });
        imagesHtml += `</div>`;
      } else {
        imagesHtml = `<div class="image-gallery"><span class="no-image">暂无图片，点击编辑/保存附件</span></div>`;
      }

      let extraResHtml = '';
      if (nonImageResources.length > 0) {
        extraResHtml +=
          '<div class="memo-resource-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; margin-top: 12px;">';
        nonImageResources.forEach((res) => {
          const filename = res.split('/').pop() || '';
          const ext = filename.split('.').pop()?.toLowerCase() || '';
          const cleanRes = this.sanitize(res);

          if (['mp3', 'wav', 'ogg', 'm4a'].includes(ext)) {
            extraResHtml += `
              <div class="resource-item audio-preview" style="grid-column: span 2; background: rgba(0,122,255,0.06); padding: 8px; border-radius: 8px; border: 1px solid rgba(0,122,255,0.15);">
                <div style="font-size: 10px; color: var(--accent-color); margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><i class="fas fa-microphone"></i> 语音附件: ${this.sanitize(
                  filename
                )}</div>
                <audio src="${cleanRes}" controls style="width: 100%; height: 28px; outline: none;"></audio>
              </div>
            `;
          } else if (['mp4', 'webm', 'mov'].includes(ext)) {
            extraResHtml += `
              <div class="resource-item video-preview" style="grid-column: span 2; border-radius: 8px; overflow: hidden; border: 1px solid var(--border-color);">
                <video src="${cleanRes}" controls poster="" style="width: 100%; max-height: 150px; background: #000; object-fit: contain;"></video>
              </div>
            `;
          } else {
            extraResHtml += `
              <div class="resource-item doc-badge" onclick="window.pywebview ? window.pywebview.api.open_office('${cleanRes}') : null" style="padding: 10px; font-size: 11px; border-radius: 8px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); display: flex; align-items: center; gap: 8px; cursor: pointer;">
                <i class="fas fa-file-alt" style="color: var(--accent-color); font-size: 16px;"></i>
                <span style="text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${this.sanitize(
                  filename
                )}</span>
              </div>
            `;
          }
        });
        extraResHtml += '</div>';
      }

      detailsHtml += imagesHtml + extraResHtml;

      const isSelected = this.selectionMode && this.selectedIds.has(memo.id);
      const checkboxHtml = `<input type="checkbox" class="card-checkbox" ${
        isSelected ? 'checked' : ''
      } onchange="window.memosManager.toggleSelect(${memo.id}, this)" />`;

      card.innerHTML = `
        <div class="card-header">
          <div class="note-title" style="flex: 1; min-width: 0;">
            ${checkboxHtml}
            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;">${this.sanitize(
              title
            )}</span>
            <span class="tag" onclick="window.memosManager.editTag(this, ${memo.id})">${this.sanitize(
        primaryTag
      )}</span>
          </div>
          <div class="note-date">${this.sanitize(date.split(' ')[0])}</div>
        </div>
        <div class="note-preview">${this.sanitize(preview)}</div>
        <div class="extra-details">${detailsHtml}</div>
        <div class="action-bar">
          <button class="btn btn-done" onclick="window.memosManager.markDone(${memo.id})">
            <i class="fas fa-check"></i> 完成
          </button>
          <button class="btn btn-image" onclick="window.memosManager.uploadImage(${memo.id})">
            <i class="fas fa-image"></i> 图片
          </button>
          <button class="btn btn-edit" onclick="window.memosManager.editNote(${memo.id})">
            <i class="fas fa-pencil-alt"></i> 编辑
          </button>
          <button class="btn btn-delete" onclick="window.memosManager.deleteMemo(${memo.id})">
            <i class="fas fa-trash"></i>
          </button>
          <button class="btn btn-expand-toggle" onclick="window.memosManager.toggleExpand(this)">
            <i class="fas fa-chevron-down"></i> <span>详情</span>
          </button>
        </div>
        ${linkCardsHtml}
      `;

      container.appendChild(card);

      if (this.expandedIds.has(memo.id)) {
        card.classList.add('expanded');
        const toggleBtn = card.querySelector('.btn-expand-toggle');
        if (toggleBtn) {
          const icon = toggleBtn.querySelector('i');
          const span = toggleBtn.querySelector('span');
          if (span) span.innerText = '收起';
          if (icon) icon.className = 'fas fa-chevron-up';
        }
      }

      if (isSelected) {
        card.classList.add('selected');
      }
    });

    container.classList.toggle('selection-mode', this.selectionMode);
    this.updateBatchInfo();
  }

  public async editTag(el: HTMLElement, noteId: number): Promise<void> {
    const current = el.textContent?.trim() || '';
    const newVal = prompt('✏️ 修改标签：', current);
    if (newVal === null) return;
    const trimmed = newVal.trim();
    if (!trimmed) {
      alert('标签不能为空！');
      return;
    }
    const tagsArray = trimmed.split(/\s+/).map((t) => (t.startsWith('#') ? t : '#' + t));
    try {
      await window.pywebview?.api.call_skill('memos', 'update', {
        id: noteId,
        tags: tagsArray,
      });
      window.showToast?.('标签更新', '标签已成功同步！', 'success');
      this.refreshMemos();
    } catch (e) {
      console.error('Failed to update tags', e);
    }
  }

  public async editDetail(el: HTMLElement, noteId: number, label: string): Promise<void> {
    const current = el.textContent?.trim() || '';
    const newVal = prompt(`✏️ 修改「${label}」：`, current);
    if (newVal === null) return;
    const trimmed = newVal.trim();
    if (!trimmed) {
      alert('内容不能为空！');
      return;
    }

    try {
      const memo = this.currentMemos.find((m) => m.id === noteId);
      if (!memo) return;

      if (label === '状态') {
        const statusTags = ['#进行中', '#未完成', '#已完成', '#待办', '#新建', '#待做'];
        let tags = memo.tags || [];
        tags = tags.filter((t) => !statusTags.includes(t));
        tags.push(trimmed.startsWith('#') ? trimmed : '#' + trimmed);
        await window.pywebview?.api.call_skill('memos', 'update', {
          id: noteId,
          tags: tags,
        });
      } else if (label === '标签') {
        const tagsArray = trimmed.split(/\s+/).map((t) => (t.startsWith('#') ? t : '#' + t));
        await window.pywebview?.api.call_skill('memos', 'update', {
          id: noteId,
          tags: tagsArray,
        });
      } else {
        await window.pywebview?.api.call_skill('memos', 'update', {
          id: noteId,
          content: trimmed,
        });
      }
      window.showToast?.('内容更新', '备忘录已成功更新！', 'success');
      this.refreshMemos();
    } catch (e) {
      console.error('Failed to update detail', e);
    }
  }

  public toggleSelectionMode(): void {
    this.selectionMode = !this.selectionMode;
    const batchBar = document.getElementById('batchBar');
    if (!this.selectionMode) {
      this.selectedIds.clear();
      if (batchBar) {
        batchBar.classList.remove('visible');
        batchBar.style.display = 'none';
      }
    } else {
      if (batchBar) {
        batchBar.classList.add('visible');
        batchBar.style.display = 'flex';
      }
    }
    const btn = document.getElementById('select-memos-btn');
    if (btn) {
      btn.classList.toggle('active', this.selectionMode);
      btn.innerHTML = this.selectionMode
        ? '<i class="fas fa-times"></i> <span>取消选择</span>'
        : '<i class="fas fa-check-double"></i> <span>选择</span>';
    }
    this.renderCurrentView();
  }

  public cancelSelection(): void {
    if (this.selectionMode) {
      this.toggleSelectionMode();
    }
  }

  public toggleSelect(noteId: number, checkbox: HTMLInputElement): void {
    if (checkbox.checked) {
      this.selectedIds.add(noteId);
    } else {
      this.selectedIds.delete(noteId);
    }
    const card = document.querySelector(`.memo-card[data-note="${noteId}"]`);
    if (card) {
      card.classList.toggle('selected', checkbox.checked);
    }
    this.updateBatchInfo();
  }

  public updateBatchInfo(): void {
    const count = this.selectedIds.size;
    const infoEl = document.getElementById('batchInfo');
    if (infoEl) infoEl.textContent = `已选择 ${count} 项`;
    const deleteBtn = document.getElementById('batchDeleteBtn') as HTMLButtonElement;
    if (deleteBtn) {
      deleteBtn.disabled = count === 0;
    }
  }

  public async deleteSelected(): Promise<void> {
    if (this.selectedIds.size === 0) return;
    if (!confirm(`确定要删除选中的 ${this.selectedIds.size} 条笔记吗？此操作不可撤销！`)) return;

    try {
      for (const id of this.selectedIds) {
        await window.pywebview?.api.call_skill('memos', 'delete', { id: id });
      }
      window.showToast?.('批量删除', `已成功删除 ${this.selectedIds.size} 条笔记。`, 'success');
      this.selectedIds.clear();

      if (this.selectionMode) {
        this.toggleSelectionMode();
      }
      this.refreshMemos();
    } catch (e: any) {
      console.error('Failed to delete selected', e);
      window.showToast?.('批量删除失败', e.message, 'error');
    }
  }

  public async markDone(id: number): Promise<void> {
    try {
      const statusTags = ['#进行中', '#未完成', '#已完成', '#待办', '#新建', '#待做'];
      const memo = this.currentMemos.find((m) => m.id === id);
      if (!memo) return;
      let tags = memo.tags || [];
      tags = tags.filter((t) => !statusTags.includes(t));
      tags.push('#已完成');
      await window.pywebview?.api.call_skill('memos', 'update', {
        id: id,
        tags: tags,
      });
      window.showToast?.('任务完成', '备忘状态已标记为「已完成」！', 'success');
      this.refreshMemos();
    } catch (e) {
      console.error(e);
    }
  }

  public uploadImage(id: number): void {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.multiple = true;
    input.onchange = async (e: Event) => {
      const files = (e.target as HTMLInputElement).files;
      if (!files || files.length === 0) return;
      let loaded = 0;
      const total = files.length;
      const tempFiles: Array<{ name: string; data: string }> = [];
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const reader = new FileReader();
        reader.onload = async (ev) => {
          tempFiles.push({ name: file.name, data: ev.target?.result as string });
          loaded++;
          if (loaded === total) {
            try {
              await window.pywebview?.api.call_skill('memos', 'update', {
                id: id,
                base64_files: tempFiles,
              });
              window.showToast?.('图片上传', '图片已成功附加到该备忘中！', 'success');
              this.refreshMemos();
            } catch (err: any) {
              console.error(err);
              window.showToast?.('上传失败', err.message, 'error');
            }
          }
        };
        reader.readAsDataURL(file);
      }
    };
    input.click();
  }

  public editNote(id: number): void {
    this.editMemoInPlace(id);
  }

  public toggleExpand(btn: HTMLElement, fromRestore: boolean = false): void {
    const card = btn.closest('.memo-card') as HTMLElement;
    if (!card) return;
    const noteId = Number(card.dataset.note);
    const isExpanded = card.classList.contains('expanded');
    if (!fromRestore) {
      if (isExpanded) {
        this.expandedIds.delete(noteId);
      } else {
        this.expandedIds.add(noteId);
      }
    }
    card.classList.toggle('expanded');
    const icon = btn.querySelector('i');
    const span = btn.querySelector('span');
    if (card.classList.contains('expanded')) {
      if (span) span.innerText = '收起';
      if (icon) icon.className = 'fas fa-chevron-up';
    } else {
      if (span) span.innerText = '详情';
      if (icon) icon.className = 'fas fa-chevron-down';
    }
  }

  public renderSpatialView(): void {
    const container = document.getElementById('memos-spatial-container');
    if (!container || !(window as any).vis) return;

    const nodes = new (window as any).vis.DataSet();
    const edges = new (window as any).vis.DataSet();
    const tagMap: Record<string, number[]> = {};

    const activeMemos = this.currentMemos.filter((m) => m.is_archived === 0);

    activeMemos.forEach((memo) => {
      nodes.add({
        id: memo.id,
        label: memo.content.substring(0, 20) + (memo.content.length > 20 ? '...' : ''),
        title: memo.content,
        color: { background: 'rgba(0, 122, 255, 0.2)', border: '#007AFF' },
        font: { color: '#ffffff' },
        shape: 'box',
        margin: 10,
      });

      if (memo.tags) {
        memo.tags.forEach((tag) => {
          if (!tagMap[tag]) tagMap[tag] = [];
          tagMap[tag].push(memo.id);
        });
      }
    });

    Object.keys(tagMap).forEach((tag) => {
      const ids = tagMap[tag];
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          edges.add({
            from: ids[i],
            to: ids[j],
            label: tag,
            color: { color: 'rgba(255,255,255,0.2)' },
            font: { size: 10, color: 'rgba(255,255,255,0.4)', strokeWidth: 0 },
          });
        }
      }
    });

    const data = { nodes, edges };
    const options = {
      physics: { enabled: true, solver: 'forceAtlas2Based' },
      interaction: { hover: true, zoomView: true },
    };

    this.network = new (window as any).vis.Network(container, data, options);
    this.network.on('click', (params: any) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const memo = this.currentMemos.find((m) => m.id === nodeId);
        if (memo) this.showMemoDetail(memo);
      }
    });
  }

  public showMemoDetail(memo: MemoData | string): void {
    let memoData: MemoData;
    if (typeof memo === 'string') {
      memoData = JSON.parse(memo);
    } else {
      memoData = memo;
    }
    const sidebar = document.getElementById('memo-detail-sidebar');
    const dateEl = document.getElementById('sidebar-memo-date');
    const contentEl = document.getElementById('sidebar-memo-content-display');
    const tagsEl = document.getElementById('sidebar-memo-tags');
    const resEl = document.getElementById('sidebar-memo-resources');

    if (!sidebar) return;
    sidebar.classList.remove('side-panel-hidden');
    if (dateEl) dateEl.innerText = '创建时间：' + new Date(memoData.created_at * 1000).toLocaleString();

    if (contentEl) {
      let html = window.marked ? window.marked.parse(memoData.content) : this.sanitize(memoData.content);
      if (window.DOMPurify) {
        html = window.DOMPurify.sanitize(html);
      }
      contentEl.innerHTML = html;
    }

    if (tagsEl) {
      tagsEl.innerHTML = (memoData.tags || [])
        .map(
          (t) =>
            `<span class="tag-item" style="cursor:pointer;" onclick="window.memosManager.filterByTag('${this.sanitize(
              t
            )}')">${this.sanitize(t)}</span>`
        )
        .join('');
    }

    if (resEl) {
      resEl.innerHTML = '';
      if (memoData.resources && memoData.resources.length > 0) {
        memoData.resources.forEach((res) => {
          const div = document.createElement('div');
          div.className = 'resource-item';
          const filename = res.split('/').pop() || '';
          div.innerHTML = `
            <div class="glass-surface" onclick="window.memosManager.openLightbox('${this.sanitize(
              res
            )}')" style="cursor:pointer; padding:6px; border-radius: 6px; font-size: 10px; display:flex; align-items:center; gap:6px; border:1px solid var(--border-color);">
              <i class="fas fa-file"></i>
              <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:80px;">${this.sanitize(
                filename
              )}</span>
            </div>
          `;
          resEl.appendChild(div);
        });
      } else {
        resEl.innerHTML = '<span style="font-size:12px; color:var(--text-secondary);">无附件</span>';
      }
    }

    const deleteBtn = document.getElementById('sidebar-delete-btn');
    if (deleteBtn) {
      deleteBtn.onclick = () => {
        this.deleteMemo(memoData.id);
        sidebar.classList.add('side-panel-hidden');
      };
    }

    const pinBtn = document.getElementById('sidebar-pin-btn');
    if (pinBtn) {
      pinBtn.innerHTML = memoData.is_pinned
        ? '<i class="fas fa-thumbtack" style="transform: rotate(45deg);"></i> 取消置顶'
        : '<i class="fas fa-thumbtack"></i> 置顶备忘';
      pinBtn.onclick = () => {
        this.togglePinStatus(memoData.id, memoData.is_pinned || 0);
        sidebar.classList.add('side-panel-hidden');
      };
    }

    const archiveBtn = document.getElementById('sidebar-archive-btn');
    if (archiveBtn) {
      archiveBtn.innerHTML = memoData.is_archived
        ? '<i class="fas fa-archive"></i> 恢复至收件箱'
        : '<i class="fas fa-archive"></i> 归档备忘录';
      archiveBtn.onclick = () => {
        this.toggleArchiveStatus(memoData.id, memoData.is_archived || 0);
        sidebar.classList.add('side-panel-hidden');
      };
    }
  }

  public renderHeatmap(): void {
    const heatmapContainer = document.getElementById('memos-heatmap-container');
    const heatmapBody = document.getElementById('memos-heatmap');
    if (!heatmapBody) return;

    heatmapContainer?.classList.remove('hidden');
    heatmapBody.innerHTML = '';

    const now = new Date();
    const days = 30;
    const counts: Record<string, number> = {};

    this.currentMemos.forEach((m) => {
      const d = new Date(m.created_at * 1000).toDateString();
      counts[d] = (counts[d] || 0) + 1;
    });

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
      if (count > 0) opacity = 0.3 + count * 0.2;
      if (opacity > 1) opacity = 1;
      box.style.background = `rgba(0, 122, 255, ${opacity})`;
      box.title = `${d.toLocaleDateString()}: ${count} 条备忘记录`;

      box.onclick = () => {
        const filterDate = d.toLocaleDateString();
        if (this.searchInput) {
          this.searchInput.value = filterDate;
          this.searchMemos(filterDate);
        }
      };

      heatmapBody.appendChild(box);
    }
  }

  public handleFiles(files: FileList): void {
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const reader = new FileReader();
      reader.onload = (e) => {
        const data = e.target?.result as string;
        this.pendingFiles.push({ name: file.name, data: data });

        const item = document.createElement('div');
        item.className = 'attachment-item';
        item.style.position = 'relative';

        const ext = file.name.split('.').pop()?.toLowerCase() || '';
        if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) {
          item.innerHTML = `<img src="${data}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px;"><div class="remove-btn" style="position: absolute; top: 2px; right: 2px; width: 18px; height: 18px; background: rgba(0,0,0,0.5); color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; cursor: pointer;">×</div>`;
        } else {
          item.innerHTML = `<div style="display: flex; align-items: center; justify-content: center; height: 100%; font-size: 24px; background: rgba(255,255,255,0.05); border-radius: 8px;"><i class="fas fa-file-alt"></i></div><div style="font-size: 8px; position: absolute; bottom: 4px; left: 4px; right: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${file.name}</div><div class="remove-btn" style="position: absolute; top: 2px; right: 2px; width: 18px; height: 18px; background: rgba(0,0,0,0.5); color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; cursor: pointer;">×</div>`;
        }

        const removeBtn = item.querySelector('.remove-btn') as HTMLElement;
        if (removeBtn) {
          removeBtn.onclick = () => {
            this.pendingFiles = this.pendingFiles.filter((f) => f.name !== file.name);
            item.remove();
          };
        }
        this.attachmentPreview?.appendChild(item);
      };
      reader.readAsDataURL(file);
    }
  }

  public async saveMemo(): Promise<void> {
    if (!this.contentInput) return;
    const content = this.contentInput.value.trim();
    const tags = this.tagsInput?.value.split(' ').filter((t) => t.startsWith('#')) || [];

    if (!content && this.pendingFiles.length === 0) return;

    try {
      if (this.currentEditingMemoId) {
        await window.pywebview?.api.call_skill('memos', 'update', {
          id: this.currentEditingMemoId,
          content: content,
          tags: tags,
          base64_files: this.pendingFiles,
        });
        window.showToast?.('更新备忘', '备忘录修缮成功！', 'success');
      } else {
        await window.pywebview?.api.call_skill('memos', 'add', {
          content: content,
          tags: tags,
          base64_files: this.pendingFiles,
        });
        window.showToast?.('保存备忘', '新灵感已存入备忘脑库中。', 'success');
      }

      this.clearEditor();
      if (this.editorContainer) {
        this.editorContainer.classList.add('hidden');
        this.editorContainer.style.display = 'none';
      }
      this.refreshMemos();
    } catch (e: any) {
      console.error(e);
      window.showToast?.('保存失败', '后端服务交互异常：' + e.message, 'error');
    }
  }

  public editMemoInPlace(id: number): void {
    const memo = this.currentMemos.find((m) => m.id === id);
    if (!memo) return;

    this.currentEditingMemoId = memo.id;

    if (this.contentInput) this.contentInput.value = memo.content;
    if (this.tagsInput) this.tagsInput.value = (memo.tags || []).join(' ');

    if (this.attachmentPreview) {
      this.attachmentPreview.innerHTML = '';
      this.pendingFiles = [];

      (memo.resources || []).forEach((res) => {
        const filename = res.split('/').pop() || '';
        const item = document.createElement('div');
        item.className = 'attachment-item';
        item.style.position = 'relative';

        const ext = filename.split('.').pop()?.toLowerCase() || '';
        if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) {
          item.innerHTML = `<img src="${res}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px;">`;
        } else {
          item.innerHTML = `<div style="display: flex; align-items: center; justify-content: center; height: 100%; font-size: 24px; background: rgba(255,255,255,0.05); border-radius: 8px;"><i class="fas fa-file-alt"></i></div><div style="font-size: 8px; position: absolute; bottom: 4px; left: 4px; right: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${filename}</div>`;
        }
        this.attachmentPreview?.appendChild(item);
      });
    }

    if (this.editorContainer) {
      this.editorContainer.classList.remove('hidden');
      this.editorContainer.style.display = 'block';
      this.contentInput?.focus();
      this.editorContainer.scrollIntoView({ behavior: 'smooth' });
    }
  }

  public async togglePinStatus(id: number, currentPinned: number): Promise<void> {
    if (!window.pywebview) return;
    const newPinned = currentPinned === 1 ? 0 : 1;
    try {
      await window.pywebview.api.call_skill('memos', 'update', {
        id: id,
        is_pinned: newPinned,
      });
      window.showToast?.('置顶更新', newPinned === 1 ? '备忘卡片已置顶' : '已取消置顶', 'success');
      this.refreshMemos();
    } catch (e) {
      console.error('Failed to pin memo', e);
    }
  }

  public async toggleArchiveStatus(id: number, currentArchived: number): Promise<void> {
    if (!window.pywebview) return;
    const newArchived = currentArchived === 1 ? 0 : 1;
    try {
      await window.pywebview.api.call_skill('memos', 'update', {
        id: id,
        is_archived: newArchived,
      });
      window.showToast?.('归档更新', newArchived === 1 ? '备忘录已归档隐藏' : '已恢复至主时间线', 'success');
      this.refreshMemos();
    } catch (e) {
      console.error('Failed to archive memo', e);
    }
  }

  public filterByTag(tag: string): void {
    if (this.searchInput) {
      this.searchInput.value = tag;
      this.searchMemos(tag);
    }
  }

  public clearEditor(): void {
    if (this.contentInput) this.contentInput.value = '';
    if (this.tagsInput) this.tagsInput.value = '';
    if (this.attachmentPreview) this.attachmentPreview.innerHTML = '';
    this.pendingFiles = [];
    this.currentEditingMemoId = null;

    document.getElementById('ai-tag-suggestion-bar')?.classList.add('hidden');
    const container = document.getElementById('ai-suggested-tags-container');
    if (container) container.innerHTML = '';
  }

  public async deleteMemo(id: number): Promise<void> {
    if (typeof window.pywebview !== 'undefined' && !confirm('确定要永久删除此备忘录吗？此操作不可撤销。')) return;
    try {
      await window.pywebview?.api.call_skill('memos', 'delete', { id });
      window.showToast?.('备忘删除', '备忘录已安全清除。', 'success');
      this.refreshMemos();
    } catch (e) {
      console.error(e);
    }
  }

  public async triggerAITagPrediction(): Promise<void> {
    const text = this.contentInput?.value.trim();
    if (!text || text.length < 15 || text.includes('#')) {
      document.getElementById('ai-tag-suggestion-bar')?.classList.add('hidden');
      return;
    }

    try {
      const predicted: string[] = await window.pywebview?.api.call_skill('memos', 'ai_tag_predict', { content: text });
      if (predicted && predicted.length > 0) {
        const container = document.getElementById('ai-suggested-tags-container');
        const bar = document.getElementById('ai-tag-suggestion-bar');
        if (container && bar) {
          container.innerHTML = '';
          predicted.forEach((tag) => {
            const chip = document.createElement('span');
            chip.className = 'suggestion-chip';
            chip.style.cssText =
              'font-size: 11px; background: rgba(88,86,214,0.15); color: #5856D6; padding: 2px 8px; border-radius: 6px; cursor: pointer; font-weight: 500;';
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
      console.error('AI Tag prediction error', e);
    }
  }

  public adoptSuggestedTag(tag: string): void {
    if (this.tagsInput) {
      const current = this.tagsInput.value.trim();
      this.tagsInput.value = current ? `${current} ${tag}` : tag;
    }
  }

  public async triggerAIMagicWand(action: string): Promise<void> {
    const text = this.contentInput?.value.trim();
    if (!text) {
      window.showToast?.('AI 魔棒', '编辑区内无文本内容可供 AI 解析！', 'error');
      return;
    }

    window.showToast?.('AI 解析中', 'AI 魔法总线正在进行深度分析与重新编排...', 'success');

    if (this.contentInput) this.contentInput.disabled = true;

    try {
      const processedText: string = await window.pywebview?.api.call_skill('memos', 'ai_magic_wand', {
        content: text,
        mode: action,
      });

      if (processedText && !processedText.startsWith('Error:') && !processedText.startsWith('AI 处理失败:')) {
        if (this.contentInput) {
          this.contentInput.value = processedText;
        }
        window.showToast?.('魔法奏效', '重新编排排版已成功渲染并覆写！', 'success');
      } else {
        window.showToast?.('魔法失败', processedText || 'AI 没有返回有效响应', 'error');
      }
    } catch (e: any) {
      console.error(e);
      window.showToast?.('AI 魔法失败', e.message, 'error');
    } finally {
      if (this.contentInput) this.contentInput.disabled = false;
    }
  }

  public handleTagAutocomplete(e: Event): void {
    const input = e.target as HTMLInputElement;
    const val = input.value;
    const lastWord = val.split(/\s+/).pop();
    const dropdown = document.getElementById('tag-autocomplete-list');

    if (!dropdown) return;

    if (lastWord && lastWord.startsWith('#') && lastWord.length > 1) {
      const prefix = lastWord.toLowerCase();
      const matches = this.allUniqueTags.filter(
        (t) => t.toLowerCase().includes(prefix) && t.toLowerCase() !== prefix
      );

      if (matches.length > 0) {
        dropdown.innerHTML = '';
        matches.forEach((tag, idx) => {
          const item = document.createElement('div');
          item.className = `autocomplete-item ${idx === 0 ? 'selected' : ''}`;
          item.style.cssText = 'padding: 6px 12px; font-size: 13px; color: var(--text-primary); cursor: pointer;';
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

  public handleTagNavigation(e: KeyboardEvent): void {
    const dropdown = document.getElementById('tag-autocomplete-list');
    if (!dropdown || dropdown.classList.contains('hidden')) return;

    const items = dropdown.querySelectorAll('.autocomplete-item');
    let selectedIdx = Array.from(items).findIndex((item) => item.classList.contains('selected'));

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
        this.selectAutocompleteTag((items[selectedIdx] as HTMLElement).innerText);
      }
    }
  }

  public selectAutocompleteTag(tag: string): void {
    if (!this.tagsInput) return;
    const words = this.tagsInput.value.split(/\s+/);
    words.pop();
    words.push(tag);
    this.tagsInput.value = words.join(' ') + ' ';
    this.tagsInput.focus();

    const dropdown = document.getElementById('tag-autocomplete-list');
    if (dropdown) {
      dropdown.classList.add('hidden');
      dropdown.style.display = 'none';
    }
  }

  public openLightbox(src: string): void {
    const lightbox = document.createElement('div');
    lightbox.style.cssText =
      'position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.9); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); z-index: 10000; display: flex; align-items: center; justify-content: center; cursor: zoom-out;';

    const img = document.createElement('img');
    img.src = src;
    img.style.cssText =
      'max-width: 90%; max-height: 85vh; border-radius: 12px; box-shadow: 0 20px 50px rgba(0,0,0,0.5); object-fit: contain; animation: scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);';

    lightbox.appendChild(img);
    lightbox.onclick = () => {
      lightbox.remove();
    };
    document.body.appendChild(lightbox);
  }
}

if (typeof window !== 'undefined') {
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    (window as any).memosManager = new MemosManager();
  } else {
    window.addEventListener('DOMContentLoaded', () => {
      (window as any).memosManager = new MemosManager();
    });
  }
}
