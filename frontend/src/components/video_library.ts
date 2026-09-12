/**
 * Butler Video Library — 媒体库浏览界面
 *
 * 集成到 Butler 2x2 矩阵 UI 的 (1,1) 象限。
 * 支持网格/列表视图、搜索、标签过滤、排序。
 *
 * 界面风格：Glassmorphism 玻璃拟态
 */

interface VideoItem {
  id: string;
  title: string;
  path: string;
  container: string;
  video_codec: string;
  audio_codec: string;
  width: number;
  height: number;
  duration: number;
  file_size: number;
  is_favorite: number;
  thumbnail_path: string;
  scanned_at: number;
}

interface LibraryStats {
  video_count: number;
  total_size_gb: number;
  total_duration_hours: number;
  favorite_count: number;
  playlist_count: number;
}

type ViewMode = 'grid' | 'list';
type SortField = 'title' | 'duration' | 'file_size' | 'scanned_at';
type SortOrder = 'ASC' | 'DESC';

class ButlerVideoLibrary {
  private container: HTMLElement;
  private apiBase: string;
  private player: ButlerVideoPlayer | null = null;

  private viewMode: ViewMode = 'grid';
  private sortField: SortField = 'title';
  private sortOrder: SortOrder = 'ASC';
  private searchQuery = '';
  private showFavoritesOnly = false;
  private currentPage = 1;
  private perPage = 50;

  private panel: HTMLElement | null = null;
  private gridEl: HTMLElement | null = null;
  private statsEl: HTMLElement | null = null;

  constructor(container: HTMLElement, apiBase: string = '') {
    this.container = container;
    this.apiBase = apiBase || window.location.origin;
    this.createPanel();
    this.loadLibrary();
  }

  setPlayer(player: ButlerVideoPlayer): void {
    this.player = player;
  }

  // ══════════════════════════════════════════
  // UI 构建
  // ══════════════════════════════════════════

  private createPanel(): void {
    this.panel = document.createElement('div');
    this.panel.className = 'bvl-panel glass-surface';
    this.panel.innerHTML = `
      <!-- 头部 -->
      <div class="bvl-header">
        <div class="bvl-header-left">
          <i class="fas fa-film"></i>
          <span class="bvl-title">媒体库</span>
        </div>
        <div class="bvl-header-right">
          <div class="bvl-search-box">
            <i class="fas fa-search"></i>
            <input type="text" class="bvl-search" placeholder="搜索视频..." />
          </div>
          <button class="bvl-btn bvl-view-grid active" title="网格视图"><i class="fas fa-grip"></i></button>
          <button class="bvl-btn bvl-view-list" title="列表视图"><i class="fas fa-list"></i></button>
          <button class="bvl-btn bvl-scan" title="扫描"><i class="fas fa-rotate"></i></button>
        </div>
      </div>

      <!-- 标签栏 -->
      <div class="bvl-tabs">
        <button class="bvl-tab active" data-tab="all"><i class="fas fa-border-all"></i> 全部</button>
        <button class="bvl-tab" data-tab="recent"><i class="fas fa-clock"></i> 最近观看</button>
        <button class="bvl-tab" data-tab="new"><i class="fas fa-sparkles"></i> 最近添加</button>
        <button class="bvl-tab" data-tab="fav"><i class="fas fa-heart"></i> 收藏</button>
      </div>

      <!-- 视频网格 -->
      <div class="bvl-grid"></div>

      <!-- 底部统计 -->
      <div class="bvl-footer">
        <span class="bvl-stats">加载中...</span>
        <div class="bvl-sort">
          <select class="bvl-sort-select">
            <option value="title_ASC">标题 A-Z</option>
            <option value="title_DESC">标题 Z-A</option>
            <option value="scanned_at_DESC">最近添加</option>
            <option value="duration_DESC">时长 ↓</option>
            <option value="file_size_DESC">大小 ↓</option>
          </select>
        </div>
      </div>
    `;

    this.container.appendChild(this.panel);

    this.gridEl = this.panel.querySelector('.bvl-grid')!;
    this.statsEl = this.panel.querySelector('.bvl-stats')!;

    this.bindEvents();
  }

  private bindEvents(): void {
    if (!this.panel) return;

    // 搜索
    const searchInput = this.panel.querySelector('.bvl-search') as HTMLInputElement;
    let searchTimer: number;
    searchInput?.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        this.searchQuery = searchInput.value.trim();
        this.currentPage = 1;
        this.loadLibrary();
      }, 300);
    });

    // 视图切换
    this.panel.querySelector('.bvl-view-grid')?.addEventListener('click', () => {
      this.viewMode = 'grid';
      this.panel!.querySelectorAll('.bvl-btn').forEach(b => b.classList.remove('active'));
      this.panel!.querySelector('.bvl-view-grid')?.classList.add('active');
      this.gridEl?.setAttribute('data-view', 'grid');
      this.loadLibrary();
    });

    this.panel.querySelector('.bvl-view-list')?.addEventListener('click', () => {
      this.viewMode = 'list';
      this.panel!.querySelectorAll('.bvl-btn').forEach(b => b.classList.remove('active'));
      this.panel!.querySelector('.bvl-view-list')?.classList.add('active');
      this.gridEl?.setAttribute('data-view', 'list');
      this.loadLibrary();
    });

    // 扫描
    this.panel.querySelector('.bvl-scan')?.addEventListener('click', () => this.triggerScan());

    // 标签
    this.panel.querySelectorAll('.bvl-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        this.panel!.querySelectorAll('.bvl-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const tabName = (tab as HTMLElement).dataset.tab;
        this.showFavoritesOnly = tabName === 'fav';
        this.currentPage = 1;
        this.loadLibrary();
      });
    });

    // 排序
    const sortSelect = this.panel.querySelector('.bvl-sort-select') as HTMLSelectElement;
    sortSelect?.addEventListener('change', () => {
      const [field, order] = sortSelect.value.split('_');
      this.sortField = field as SortField;
      this.sortOrder = order as SortOrder;
      this.currentPage = 1;
      this.loadLibrary();
    });
  }

  // ══════════════════════════════════════════
  // 数据加载
  // ══════════════════════════════════════════

  async loadLibrary(): Promise<void> {
    try {
      const params = new URLSearchParams({
        search: this.searchQuery,
        sort: this.sortField,
        order: this.sortOrder,
        page: this.currentPage.toString(),
        per_page: this.perPage.toString(),
        favorite: this.showFavoritesOnly.toString(),
      });

      const res = await fetch(`${this.apiBase}/api/video/library?${params}`);
      const json = await res.json();

      if (json.success && json.data) {
        this.renderGrid(json.data.videos);
        this.updateStats(json.data);
      }
    } catch (e) {
      console.error('加载媒体库失败:', e);
    }
  }

  async loadStats(): Promise<void> {
    try {
      const res = await fetch(`${this.apiBase}/api/video/library/stats`);
      const json = await res.json();
      if (json.success && json.data) {
        const s = json.data as LibraryStats;
        if (this.statsEl) {
          this.statsEl.textContent =
            `共 ${s.video_count} 个视频 · ${s.total_size_gb} GB · ${s.total_duration_hours}h · ` +
            `❤️ ${s.favorite_count} · 📋 ${s.playlist_count}`;
        }
      }
    } catch {}
  }

  async triggerScan(): Promise<void> {
    const scanBtn = this.panel?.querySelector('.bvl-scan i');
    if (scanBtn) scanBtn.className = 'fas fa-spinner fa-spin';
    try {
      const res = await fetch(`${this.apiBase}/api/video/scan`, { method: 'POST' });
      const json = await res.json();
      if (json.success) {
        this.loadLibrary();
        this.loadStats();
      }
    } catch (e) {
      console.error('扫描失败:', e);
    } finally {
      if (scanBtn) scanBtn.className = 'fas fa-rotate';
    }
  }

  // ══════════════════════════════════════════
  // 渲染
  // ══════════════════════════════════════════

  private renderGrid(videos: VideoItem[]): void {
    if (!this.gridEl) return;

    if (videos.length === 0) {
      this.gridEl.innerHTML = `
        <div class="bvl-empty">
          <i class="fas fa-film"></i>
          <p>还没有视频</p>
          <p>点击右上角扫描按钮添加视频目录</p>
        </div>
      `;
      return;
    }

    this.gridEl.innerHTML = videos.map(v => this.renderCard(v)).join('');

    // 绑定点击事件
    this.gridEl.querySelectorAll('.bvl-card').forEach(card => {
      card.addEventListener('click', () => {
        const videoId = (card as HTMLElement).dataset.videoId;
        if (videoId) this.playVideo(videoId);
      });
    });

    // 绑定收藏按钮
    this.gridEl.querySelectorAll('.bvl-card-fav').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const videoId = (btn as HTMLElement).dataset.videoId;
        if (videoId) this.toggleFavorite(videoId, btn as HTMLElement);
      });
    });

    this.gridEl.setAttribute('data-view', this.viewMode);
  }

  private renderCard(v: VideoItem): string {
    const resLabel = this.getResolutionLabel(v.height);
    const durLabel = this.formatDuration(v.duration);
    const sizeLabel = this.formatSize(v.file_size);
    const codecLabel = (v.video_codec || '').toUpperCase();
    const favClass = v.is_favorite ? 'active' : '';
    const favIcon = v.is_favorite ? 'fas fa-heart' : 'far fa-heart';

    if (this.viewMode === 'list') {
      return `
        <div class="bvl-card bvl-card-list" data-video-id="${v.id}">
          <div class="bvl-card-icon"><i class="fas fa-play-circle"></i></div>
          <div class="bvl-card-info">
            <div class="bvl-card-title">${this.escapeHtml(v.title)}</div>
            <div class="bvl-card-meta">
              <span>${resLabel}</span>
              <span>${codecLabel}</span>
              <span>${durLabel}</span>
              <span>${sizeLabel}</span>
            </div>
          </div>
          <button class="bvl-card-fav ${favClass}" data-video-id="${v.id}">
            <i class="${favIcon}"></i>
          </button>
        </div>
      `;
    }

    return `
      <div class="bvl-card bvl-card-grid" data-video-id="${v.id}">
        <div class="bvl-card-thumb">
          <i class="fas fa-play-circle"></i>
          <span class="bvl-card-duration">${durLabel}</span>
        </div>
        <div class="bvl-card-body">
          <div class="bvl-card-title">${this.escapeHtml(v.title)}</div>
          <div class="bvl-card-meta">
            <span>${resLabel}</span>
            <span>${codecLabel}</span>
            <span>${sizeLabel}</span>
          </div>
        </div>
        <button class="bvl-card-fav ${favClass}" data-video-id="${v.id}">
          <i class="${favIcon}"></i>
        </button>
      </div>
    `;
  }

  private updateStats(data: any): void {
    if (this.statsEl && data) {
      this.statsEl.textContent =
        `共 ${data.total || 0} 个视频 · 第 ${data.page || 1}/${data.pages || 1} 页`;
    }
  }

  // ══════════════════════════════════════════
  // 操作
  // ══════════════════════════════════════════

  private async playVideo(videoId: string): Promise<void> {
    if (this.player) {
      this.player.show();
      await this.player.playVideo(videoId);
    } else {
      // 直接 API 调用
      try {
        await fetch(`${this.apiBase}/api/video/play/${videoId}`, { method: 'POST' });
      } catch (e) {
        console.error('播放失败:', e);
      }
    }
  }

  private async toggleFavorite(videoId: string, btn: HTMLElement): Promise<void> {
    try {
      const res = await fetch(`${this.apiBase}/api/video/${videoId}/favorite`, { method: 'POST' });
      const json = await res.json();
      if (json.success) {
        const isFav = json.data.is_favorite;
        btn.classList.toggle('active', isFav);
        const icon = btn.querySelector('i');
        if (icon) icon.className = isFav ? 'fas fa-heart' : 'far fa-heart';
      }
    } catch {}
  }

  // ══════════════════════════════════════════
  // 工具函数
  // ══════════════════════════════════════════

  private getResolutionLabel(height: number): string {
    if (height >= 2160) return '4K';
    if (height >= 1440) return '2K';
    if (height >= 1080) return '1080p';
    if (height >= 720) return '720p';
    if (height >= 480) return '480p';
    return height > 0 ? `${height}p` : '-';
  }

  private formatDuration(seconds: number): string {
    if (!seconds || seconds <= 0) return '-';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return `${h}h${m.toString().padStart(2, '0')}m`;
    return `${m}m`;
  }

  private formatSize(bytes: number): string {
    if (!bytes || bytes <= 0) return '-';
    const gb = bytes / (1024 ** 3);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    return `${(bytes / (1024 ** 2)).toFixed(0)} MB`;
  }

  private escapeHtml(str: string): string {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  destroy(): void {
    this.panel?.remove();
  }
}
