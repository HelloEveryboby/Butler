/**
 * Butler In-App Browser Component in TypeScript
 *
 * Feature set:
 *   - Multi-tab (create / switch / close, each tab has its own iframe + history)
 *   - Smart address bar (auto-detect URL vs search engine query)
 *   - Bookmarks (star button + side panel + localStorage persistence)
 *   - Searchable history (side panel + persistence + clear-all)
 *   - Page comments (per-tab, persisted)
 *   - Site allow/block list
 *   - Backwards-compatible public API: open / close / navigate / reload /
 *     goBack / goForward / capturePage / blockSite / unblockSite /
 *     allowSite / disallowSite / getNetworkLogs / getConsoleLogs / destroy
 */

interface BrowserComment {
  text: string;
  url: string;
  timestamp: number;
  tabId: string;
}

interface BrowserSettings {
  blockedSites: string[];
  allowedSites: string[];
  searchEngine: string;
}

interface BrowserTab {
  id: string;
  url: string;
  title: string;
  history: string[];
  historyIndex: number;
  iframe: HTMLIFrameElement | null;
  placeholder: HTMLElement | null;
  loading: boolean;
}

interface BookmarkEntry {
  url: string;
  title: string;
  addedAt: number;
}

interface HistoryEntry {
  url: string;
  title: string;
  visitedAt: number;
  tabId: string;
}

const BROWSER_STORAGE_KEYS = {
  settings: 'butler_browser_settings',
  bookmarks: 'butler_browser_bookmarks',
  history: 'butler_browser_history',
  comments: 'butler_browser_comments',
} as const;

const BROWSER_LIMITS = {
  maxHistoryPerTab: 50,
  maxGlobalHistory: 500,
  maxComments: 200,
} as const;

class InAppBrowser {
  public containerId: string;
  public container: HTMLElement | null = null;
  public tabBar: HTMLElement | null = null;
  public tabList: HTMLElement | null = null;
  public newTabBtn: HTMLElement | null = null;
  public addressBar: HTMLInputElement | null = null;
  public backBtn: HTMLElement | null = null;
  public forwardBtn: HTMLElement | null = null;
  public refreshBtn: HTMLElement | null = null;
  public bookmarkToggleBtn: HTMLElement | null = null;
  public bookmarksPanelBtn: HTMLElement | null = null;
  public historyPanelBtn: HTMLElement | null = null;
  public commentBtn: HTMLElement | null = null;
  public closeBtn: HTMLElement | null = null;
  public statusUrl: HTMLElement | null = null;
  public commentsPanel: HTMLElement | null = null;
  public commentsList: HTMLElement | null = null;
  public commentInput: HTMLTextAreaElement | null = null;
  public commentSubmit: HTMLElement | null = null;
  public commentsClose: HTMLElement | null = null;
  public bookmarksPanel: HTMLElement | null = null;
  public bookmarksList: HTMLElement | null = null;
  public bookmarksClose: HTMLElement | null = null;
  public historyPanel: HTMLElement | null = null;
  public historySearchInput: HTMLInputElement | null = null;
  public historyList: HTMLElement | null = null;
  public historyClearBtn: HTMLElement | null = null;
  public historyClose: HTMLElement | null = null;
  public contentArea: HTMLElement | null = null;

  public tabs: BrowserTab[] = [];
  public activeTabId: string | null = null;
  public bookmarks: BookmarkEntry[] = [];
  public historyEntries: HistoryEntry[] = [];
  public comments: BrowserComment[] = [];
  public blockedSites: string[] = [];
  public allowedSites: string[] = [];
  public searchEngine: string = 'https://duckduckgo.com/?q=';
  public isOpen: boolean = false;

  public onComment: ((comment: BrowserComment) => void) | null = null;
  public onPageLoad: ((url: string) => void) | null = null;
  public onError: ((err: string) => void) | null = null;

  private _networkLogs: any[] = [];
  private _consoleLogs: any[] = [];
  private _tabSeq: number = 0;

  constructor(containerId: string) {
    this.containerId = containerId;
    this._loadSettings();
    this._loadBookmarks();
    this._loadHistory();
    this._loadComments();
    this._buildUI();
    this._createTab('about:blank');
  }

  // ---------- Persistence ----------

  private _loadSettings(): void {
    try {
      const raw = localStorage.getItem(BROWSER_STORAGE_KEYS.settings);
      if (raw) {
        const parsed: BrowserSettings = JSON.parse(raw);
        this.blockedSites = parsed.blockedSites || [];
        this.allowedSites = parsed.allowedSites || [];
        if (parsed.searchEngine) this.searchEngine = parsed.searchEngine;
      }
    } catch (e) {
      console.warn('浏览器设置加载失败:', e);
    }
  }

  private _saveSettings(): void {
    try {
      localStorage.setItem(
        BROWSER_STORAGE_KEYS.settings,
        JSON.stringify({
          blockedSites: this.blockedSites,
          allowedSites: this.allowedSites,
          searchEngine: this.searchEngine,
        } as BrowserSettings)
      );
    } catch (e) {
      console.warn('浏览器设置保存失败:', e);
    }
  }

  private _loadBookmarks(): void {
    try {
      const raw = localStorage.getItem(BROWSER_STORAGE_KEYS.bookmarks);
      if (raw) this.bookmarks = JSON.parse(raw) || [];
    } catch (e) {
      console.warn('书签加载失败:', e);
      this.bookmarks = [];
    }
  }

  private _saveBookmarks(): void {
    try {
      localStorage.setItem(BROWSER_STORAGE_KEYS.bookmarks, JSON.stringify(this.bookmarks));
    } catch (e) {
      console.warn('书签保存失败:', e);
    }
  }

  private _loadHistory(): void {
    try {
      const raw = localStorage.getItem(BROWSER_STORAGE_KEYS.history);
      if (raw) this.historyEntries = JSON.parse(raw) || [];
    } catch (e) {
      console.warn('历史记录加载失败:', e);
      this.historyEntries = [];
    }
  }

  private _saveHistory(): void {
    try {
      localStorage.setItem(BROWSER_STORAGE_KEYS.history, JSON.stringify(this.historyEntries));
    } catch (e) {
      console.warn('历史记录保存失败:', e);
    }
  }

  private _loadComments(): void {
    try {
      const raw = localStorage.getItem(BROWSER_STORAGE_KEYS.comments);
      if (raw) this.comments = JSON.parse(raw) || [];
    } catch (e) {
      console.warn('评论加载失败:', e);
      this.comments = [];
    }
  }

  private _saveComments(): void {
    try {
      const trimmed = this.comments.slice(-BROWSER_LIMITS.maxComments);
      localStorage.setItem(BROWSER_STORAGE_KEYS.comments, JSON.stringify(trimmed));
    } catch (e) {
      console.warn('评论保存失败:', e);
    }
  }

  // ---------- UI Construction ----------

  private _buildUI(): void {
    this.container = document.getElementById(this.containerId);
    if (!this.container) return;

    this.container.innerHTML = `
      <div class="butler-browser" style="
          position: absolute; top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(20, 20, 30, 0.98);
          border-radius: 12px; overflow: hidden;
          display: flex; flex-direction: column;
          z-index: 10000; box-shadow: 0 20px 60px rgba(0,0,0,0.4);
      ">
        <div class="browser-tabbar" style="
            display: flex; align-items: center; gap: 4px;
            padding: 6px 8px; background: #15151f;
            border-bottom: 1px solid rgba(255,255,255,0.06);
            overflow-x: auto;
        ">
          <div class="browser-tablist" style="
              display: flex; align-items: center; gap: 4px;
              flex: 1; min-height: 28px;
          "></div>
          <button class="browser-newtab" title="新标签页 (Ctrl+T)" style="
              background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
              border-radius: 6px; color: rgba(255,255,255,0.85);
              width: 28px; height: 28px; cursor: pointer; font-size: 14px;
              display: flex; align-items: center; justify-content: center; flex-shrink: 0;
          "><i class="fas fa-plus"></i></button>
        </div>

        <div class="browser-toolbar" style="
            display: flex; align-items: center; gap: 8px;
            padding: 10px 14px;
            background: linear-gradient(180deg, #2a2a3a 0%, #1e1e2e 100%);
            border-bottom: 1px solid rgba(255,255,255,0.1);
        ">
          <button class="browser-btn browser-back" title="后退 (Alt+←)" style="${this._btnStyle()}">
            <i class="fas fa-chevron-left"></i>
          </button>
          <button class="browser-btn browser-forward" title="前进 (Alt+→)" style="${this._btnStyle()}">
            <i class="fas fa-chevron-right"></i>
          </button>
          <button class="browser-btn browser-refresh" title="刷新 (Ctrl+R)" style="${this._btnStyle()}">
            <i class="fas fa-sync-alt"></i>
          </button>
          <div class="browser-address-container" style="
              flex: 1; display: flex; align-items: center;
              background: rgba(255,255,255,0.08); border-radius: 8px;
              padding: 4px 12px; gap: 8px;
          ">
            <i class="fas fa-lock browser-secure-icon" style="color: #34C759; font-size: 11px;"></i>
            <input type="text" class="browser-address" placeholder="输入 URL 或搜索..."
                style="flex: 1; background: transparent; border: none; outline: none;
                color: #fff; font-size: 13px; font-family: inherit;" />
            <button class="browser-btn browser-bookmark-toggle" title="收藏此页 (Ctrl+D)" style="
                background: transparent; border: none; color: rgba(255,255,255,0.5);
                cursor: pointer; padding: 2px 4px; font-size: 13px;
            "><i class="far fa-star"></i></button>
          </div>
          <button class="browser-btn browser-bookmarks" title="书签" style="${this._btnStyle()}">
            <i class="fas fa-bookmark"></i>
          </button>
          <button class="browser-btn browser-history" title="历史 (Ctrl+Y)" style="${this._btnStyle()}">
            <i class="fas fa-history"></i>
          </button>
          <button class="browser-btn browser-comment" title="页面评论" style="${this._btnStyle()}">
            <i class="fas fa-comment-dots"></i>
          </button>
          <button class="browser-btn browser-close" title="关闭" style="${this._btnStyle()}">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="browser-content" style="
            flex: 1; position: relative; background: #fff; overflow: hidden;
        "></div>

        <div class="browser-status" style="
            display: flex; align-items: center; padding: 6px 14px;
            background: #1a1a28; border-top: 1px solid rgba(255,255,255,0.08);
            font-size: 11px; color: rgba(255,255,255,0.6); gap: 12px;
        ">
          <span class="browser-status-url"></span>
          <span class="browser-status-separator">·</span>
          <span class="browser-status-secure"><i class="fas fa-shield-alt"></i> 安全浏览</span>
        </div>

        <div class="browser-comments-panel" style="
            position: absolute; top: 60px; right: -340px;
            width: 320px; height: calc(100% - 100px);
            background: rgba(25,25,35,0.98);
            border-left: 1px solid rgba(255,255,255,0.1);
            padding: 16px; transition: right 0.3s ease;
            overflow-y: auto; z-index: 100;
            display: flex; flex-direction: column;
        ">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-weight: 600; font-size: 14px;">页面评论</div>
            <button class="comments-close" style="background: none; border: none; color: rgba(255,255,255,0.6); cursor: pointer;">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="comments-list" style="display: flex; flex-direction: column; gap: 8px; flex: 1; overflow-y: auto;"></div>
          <div class="comment-input-area" style="margin-top: 12px;">
            <textarea class="comment-input" placeholder="添加评论（关联当前页面 URL）..."
                style="width: 100%; min-height: 60px; background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.1); border-radius: 8px;
                padding: 10px; color: #fff; font-size: 12px; resize: vertical;"></textarea>
            <button class="comment-submit" style="
                margin-top: 8px; width: 100%; padding: 8px;
                background: linear-gradient(135deg, #6366f1, #8b5cf6);
                border: none; border-radius: 6px; color: #fff;
                font-size: 12px; cursor: pointer; font-weight: 500;
            ">提交评论</button>
          </div>
        </div>

        <div class="browser-bookmarks-panel" style="
            position: absolute; top: 60px; right: -340px;
            width: 320px; height: calc(100% - 100px);
            background: rgba(25,25,35,0.98);
            border-left: 1px solid rgba(255,255,255,0.1);
            padding: 16px; transition: right 0.3s ease;
            overflow-y: auto; z-index: 100;
            display: flex; flex-direction: column;
        ">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-weight: 600; font-size: 14px;"><i class="fas fa-bookmark" style="color: #FF9500; margin-right: 6px;"></i>书签</div>
            <button class="bookmarks-close" style="background: none; border: none; color: rgba(255,255,255,0.6); cursor: pointer;">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="bookmarks-list" style="display: flex; flex-direction: column; gap: 6px; flex: 1; overflow-y: auto;"></div>
        </div>

        <div class="browser-history-panel" style="
            position: absolute; top: 60px; right: -340px;
            width: 320px; height: calc(100% - 100px);
            background: rgba(25,25,35,0.98);
            border-left: 1px solid rgba(255,255,255,0.1);
            padding: 16px; transition: right 0.3s ease;
            overflow-y: auto; z-index: 100;
            display: flex; flex-direction: column;
        ">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-weight: 600; font-size: 14px;"><i class="fas fa-history" style="color: #5856D6; margin-right: 6px;"></i>历史记录</div>
            <button class="history-close" style="background: none; border: none; color: rgba(255,255,255,0.6); cursor: pointer;">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <input type="text" class="history-search" placeholder="搜索历史..."
              style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
              border-radius: 8px; padding: 8px 12px; color: #fff; font-size: 13px; margin-bottom: 10px;" />
          <div class="history-list" style="display: flex; flex-direction: column; gap: 4px; flex: 1; overflow-y: auto;"></div>
          <button class="history-clear" style="
              margin-top: 10px; padding: 8px; width: 100%;
              background: rgba(255,59,48,0.12); border: 1px solid rgba(255,59,48,0.3);
              border-radius: 6px; color: #FF3B30; font-size: 12px;
              cursor: pointer; font-weight: 500;
          "><i class="fas fa-trash-alt" style="margin-right: 6px;"></i>清空全部历史</button>
        </div>
      </div>
    `;

    // Wire up element references
    this.tabBar = this.container.querySelector('.browser-tabbar');
    this.tabList = this.container.querySelector('.browser-tablist');
    this.newTabBtn = this.container.querySelector('.browser-newtab');
    this.contentArea = this.container.querySelector('.browser-content');
    this.addressBar = this.container.querySelector('.browser-address');
    this.backBtn = this.container.querySelector('.browser-back');
    this.forwardBtn = this.container.querySelector('.browser-forward');
    this.refreshBtn = this.container.querySelector('.browser-refresh');
    this.bookmarkToggleBtn = this.container.querySelector('.browser-bookmark-toggle');
    this.bookmarksPanelBtn = this.container.querySelector('.browser-bookmarks');
    this.historyPanelBtn = this.container.querySelector('.browser-history');
    this.commentBtn = this.container.querySelector('.browser-comment');
    this.closeBtn = this.container.querySelector('.browser-close');
    this.statusUrl = this.container.querySelector('.browser-status-url');
    this.commentsPanel = this.container.querySelector('.browser-comments-panel');
    this.commentsList = this.container.querySelector('.comments-list');
    this.commentInput = this.container.querySelector('.comment-input');
    this.commentSubmit = this.container.querySelector('.comment-submit');
    this.commentsClose = this.container.querySelector('.comments-close');
    this.bookmarksPanel = this.container.querySelector('.browser-bookmarks-panel');
    this.bookmarksList = this.container.querySelector('.bookmarks-list');
    this.bookmarksClose = this.container.querySelector('.bookmarks-close');
    this.historyPanel = this.container.querySelector('.browser-history-panel');
    this.historySearchInput = this.container.querySelector('.history-search');
    this.historyList = this.container.querySelector('.history-list');
    this.historyClearBtn = this.container.querySelector('.history-clear');
    this.historyClose = this.container.querySelector('.history-close');

    this._bindEvents();
  }

  private _btnStyle(): string {
    return `
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 6px;
      color: rgba(255,255,255,0.8);
      padding: 6px 10px;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
    `;
  }

  private _bindEvents(): void {
    this.newTabBtn?.addEventListener('click', () => this.newTab());
    this.backBtn?.addEventListener('click', () => this.goBack());
    this.forwardBtn?.addEventListener('click', () => this.goForward());
    this.refreshBtn?.addEventListener('click', () => this.reload());
    this.closeBtn?.addEventListener('click', () => this.close());
    this.commentBtn?.addEventListener('click', () => this.toggleComments());
    this.commentsClose?.addEventListener('click', () => this.toggleComments());
    this.bookmarksPanelBtn?.addEventListener('click', () => this.toggleBookmarksPanel());
    this.bookmarksClose?.addEventListener('click', () => this.toggleBookmarksPanel());
    this.historyPanelBtn?.addEventListener('click', () => this.toggleHistoryPanel());
    this.historyClose?.addEventListener('click', () => this.toggleHistoryPanel());
    this.historyClearBtn?.addEventListener('click', () => this.clearHistory());

    this.bookmarkToggleBtn?.addEventListener('click', () => this.toggleBookmarkCurrent());

    this.addressBar?.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.navigate((e.target as HTMLInputElement).value);
      }
    });

    this.historySearchInput?.addEventListener('input', () => {
      this._renderHistory(this.historySearchInput?.value || '');
    });

    this.commentSubmit?.addEventListener('click', () => {
      const text = this.commentInput?.value.trim() || '';
      if (text) {
        this._addComment(text);
        if (this.commentInput) this.commentInput.value = '';
      }
    });

    // Global keyboard shortcuts (active only when browser is open)
    this.container?.addEventListener('keydown', (e: KeyboardEvent) => this._handleShortcut(e));

    this.container?.querySelectorAll('.browser-btn').forEach((btn) => {
      const el = btn as HTMLElement;
      el.addEventListener('mouseenter', () => {
        el.style.background = 'rgba(255,255,255,0.12)';
      });
      el.addEventListener('mouseleave', () => {
        el.style.background = 'rgba(255,255,255,0.06)';
      });
    });
  }

  private _handleShortcut(e: KeyboardEvent): void {
    const ctrl = e.ctrlKey || e.metaKey;
    if (ctrl && e.key === 't') {
      e.preventDefault();
      this.newTab();
      this.addressBar?.focus();
    } else if (ctrl && e.key === 'w') {
      e.preventDefault();
      this.closeTab(this.activeTabId || '');
    } else if (ctrl && e.key === 'd') {
      e.preventDefault();
      this.toggleBookmarkCurrent();
    } else if (ctrl && e.key === 'y') {
      e.preventDefault();
      this.toggleHistoryPanel();
    } else if (ctrl && e.key === 'r') {
      e.preventDefault();
      this.reload();
    } else if (e.altKey && e.key === 'ArrowLeft') {
      e.preventDefault();
      this.goBack();
    } else if (e.altKey && e.key === 'ArrowRight') {
      e.preventDefault();
      this.goForward();
    }
  }

  // ---------- Tab Management ----------

  private _genTabId(): string {
    this._tabSeq += 1;
    return `bt-${Date.now().toString(36)}-${this._tabSeq}`;
  }

  public newTab(url: string = 'about:blank'): BrowserTab | null {
    return this._createTab(url);
  }

  private _createTab(url: string): BrowserTab | null {
    if (!this.contentArea) return null;
    const tab: BrowserTab = {
      id: this._genTabId(),
      url: url || 'about:blank',
      title: url && url !== 'about:blank' ? this._displayUrl(url) : '新标签页',
      history: url && url !== 'about:blank' ? [url] : [],
      historyIndex: url && url !== 'about:blank' ? 0 : -1,
      iframe: null,
      placeholder: null,
      loading: false,
    };

    // Build iframe + placeholder for this tab
    const iframe = document.createElement('iframe');
    iframe.className = 'browser-iframe';
    iframe.style.cssText =
      'width: 100%; height: 100%; border: none; background: #fff; display: none;';
    iframe.setAttribute(
      'sandbox',
      'allow-same-origin allow-scripts allow-forms allow-popups allow-modals allow-downloads'
    );

    const placeholder = document.createElement('div');
    placeholder.className = 'browser-placeholder';
    placeholder.style.cssText = `
      position: absolute; inset: 0;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      color: rgba(255,255,255,0.5);
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      gap: 16px;
    `;
    placeholder.innerHTML = `
      <i class="fas fa-globe" style="font-size: 48px; opacity: 0.3;"></i>
      <div style="font-size: 16px;">输入 URL 或搜索开始浏览</div>
      <div style="font-size: 12px; opacity: 0.6;">支持本地开发服务器、文件预览与网络搜索</div>
      <div style="font-size: 11px; opacity: 0.4; margin-top: 8px;">
        快捷键: Ctrl+T 新标签 · Ctrl+D 收藏 · Ctrl+Y 历史
      </div>
    `;

    iframe.addEventListener('load', () => {
      if (!tab.iframe) return;
      const currentUrl = tab.iframe.src;
      tab.url = currentUrl;
      tab.loading = false;
      try {
        const doc = tab.iframe.contentDocument || tab.iframe.contentWindow?.document;
        if (doc && doc.title) tab.title = doc.title;
      } catch {
        // cross-origin — keep display URL as title
      }
      this._updateAddressBar(currentUrl);
      this._updateStatusUrl(currentUrl);
      this._updateNavButtons();
      this._renderTabs();
      if (currentUrl && currentUrl !== 'about:blank') {
        this._recordHistory(currentUrl, tab.title, tab.id);
      }
      if (this.onPageLoad) this.onPageLoad(currentUrl);
    });

    iframe.addEventListener('error', () => {
      console.warn('iframe 加载出错');
      tab.loading = false;
    });

    this.contentArea.appendChild(placeholder);
    this.contentArea.appendChild(iframe);
    tab.iframe = iframe;
    tab.placeholder = placeholder;

    this.tabs.push(tab);
    this._switchToTab(tab.id);
    this._renderTabs();

    if (url && url !== 'about:blank') {
      tab.iframe.src = url;
    }

    return tab;
  }

  public closeTab(tabId: string): void {
    const idx = this.tabs.findIndex((t) => t.id === tabId);
    if (idx === -1) return;
    const tab = this.tabs[idx];
    tab.iframe?.remove();
    tab.placeholder?.remove();
    this.tabs.splice(idx, 1);

    if (this.tabs.length === 0) {
      // Always keep at least one tab; recreate a blank one
      this._createTab('about:blank');
      return;
    }

    if (this.activeTabId === tabId) {
      const nextIdx = Math.max(0, idx - 1);
      this._switchToTab(this.tabs[nextIdx].id);
    }
    this._renderTabs();
  }

  public switchTab(tabId: string): void {
    this._switchToTab(tabId);
  }

  private _switchToTab(tabId: string): void {
    this.activeTabId = tabId;
    for (const t of this.tabs) {
      const isActive = t.id === tabId;
      if (t.iframe) t.iframe.style.display = isActive ? 'block' : 'none';
      if (t.placeholder) t.placeholder.style.display = isActive ? 'flex' : 'none';
    }
    const active = this._getActiveTab();
    if (active) {
      this._updateAddressBar(active.url);
      this._updateStatusUrl(active.url);
      this._updateNavButtons();
      this._updateBookmarkToggle(active.url);
    }
    this._renderTabs();
  }

  private _getActiveTab(): BrowserTab | null {
    return this.tabs.find((t) => t.id === this.activeTabId) || null;
  }

  private _renderTabs(): void {
    if (!this.tabList) return;
    this.tabList.innerHTML = '';
    for (const t of this.tabs) {
      const el = document.createElement('div');
      const isActive = t.id === this.activeTabId;
      el.style.cssText = `
        display: flex; align-items: center; gap: 6px;
        padding: 4px 10px; border-radius: 6px;
        background: ${isActive ? 'rgba(99,102,241,0.18)' : 'rgba(255,255,255,0.04)'};
        border: 1px solid ${isActive ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.06)'};
        color: ${isActive ? '#fff' : 'rgba(255,255,255,0.7)'};
        font-size: 12px; cursor: pointer; max-width: 180px;
        transition: background 0.15s;
      `;
      el.innerHTML = `
        <i class="fas fa-circle" style="font-size: 6px; color: ${t.loading ? '#34C759' : 'rgba(255,255,255,0.3)'}; ${t.loading ? 'animation: pulse 1s infinite;' : ''}"></i>
        <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 120px;">${this._escape(t.title) || '新标签页'}</span>
        <i class="fas fa-times tab-close" style="font-size: 10px; padding: 2px; border-radius: 3px;"></i>
      `;
      el.addEventListener('click', (e) => {
        const target = e.target as HTMLElement;
        if (target.classList.contains('tab-close') || target.closest('.tab-close')) {
          this.closeTab(t.id);
        } else {
          this._switchToTab(t.id);
        }
      });
      this.tabList?.appendChild(el);
    }
  }

  private _updateNavButtons(): void {
    const t = this._getActiveTab();
    if (!t) return;
    if (this.backBtn) {
      this.backBtn.style.opacity = t.historyIndex > 0 ? '1' : '0.4';
      this.backBtn.style.pointerEvents = t.historyIndex > 0 ? 'auto' : 'none';
    }
    if (this.forwardBtn) {
      this.forwardBtn.style.opacity = t.historyIndex < t.history.length - 1 ? '1' : '0.4';
      this.forwardBtn.style.pointerEvents = t.historyIndex < t.history.length - 1 ? 'auto' : 'none';
    }
  }

  private _updateAddressBar(url: string): void {
    if (this.addressBar) this.addressBar.value = url && url !== 'about:blank' ? url : '';
  }

  private _updateStatusUrl(url: string): void {
    if (this.statusUrl) this.statusUrl.textContent = this._displayUrl(url);
  }

  private _updateBookmarkToggle(url: string): void {
    const icon = this.bookmarkToggleBtn?.querySelector('i');
    if (!icon) return;
    const isMarked = url && url !== 'about:blank' && this.isBookmarked(url);
    icon.className = isMarked ? 'fas fa-star' : 'far fa-star';
    icon.style.color = isMarked ? '#FF9500' : 'rgba(255,255,255,0.5)';
  }

  // ---------- Smart Address Bar ----------

  /**
   * Decide whether the user-typed input is a URL or a search query.
   *  - "http(s)://" / "file://" / "about:" → URL as-is
   *  - "localhost:port" / IPv4 / domain with TLD → prepend https://
   *  - anything else → search engine query
   */
  private _normalizeInput(input: string): { url: string; isSearch: boolean } {
    const trimmed = (input || '').trim();
    if (!trimmed) return { url: 'about:blank', isSearch: false };

    // Already has an explicit protocol
    if (/^(https?:\/\/|file:\/\/|about:)/i.test(trimmed)) {
      return { url: trimmed, isSearch: false };
    }

    // Looks like a domain or local address (no spaces, has a dot or is localhost)
    const looksLikeHost =
      !/\s/.test(trimmed) &&
      (/^localhost(:\d+)?(\/.*)?$/i.test(trimmed) ||
        /^(\d{1,3}\.){3}\d{1,3}(:\d+)?(\/.*)?$/i.test(trimmed) ||
        /^([a-z0-9-]+\.)+[a-z]{2,}(\/.*)?$/i.test(trimmed));

    if (looksLikeHost) {
      return { url: 'https://' + trimmed, isSearch: false };
    }
    return { url: this.searchEngine + encodeURIComponent(trimmed), isSearch: true };
  }

  private _isUrlAllowed(url: string): boolean {
    if (!url || url === 'about:blank') return true;
    if (this.blockedSites.some((site) => url.includes(site))) return false;
    if (this.allowedSites.length > 0) {
      return this.allowedSites.some((site) => url.includes(site));
    }
    return true;
  }

  // ---------- Public Navigation API ----------

  public navigate(input: string): void {
    if (!input) return;
    const { url, isSearch } = this._normalizeInput(input);
    if (!url) return;

    if (!this._isUrlAllowed(url)) {
      console.warn(`网站被屏蔽: ${url}`);
      if (this.onError) this.onError(`该网站已被屏蔽: ${url}`);
      window.showToast?.('浏览器', `该网站已被屏蔽: ${url}`, 'error');
      return;
    }

    const tab = this._getActiveTab() || this._createTab('about:blank');
    if (!tab || !tab.iframe) return;

    tab.loading = true;
    if (tab.placeholder) tab.placeholder.style.display = 'none';
    tab.iframe.src = url;
    tab.url = url;
    tab.title = isSearch ? `搜索: ${input.trim()}` : this._displayUrl(url);
    if (this.addressBar) this.addressBar.value = url;
    this._updateBookmarkToggle(url);
    this._renderTabs();

    // Update per-tab history immediately; iframe load will record global history
    this._updateTabHistory(tab, url);
  }

  public goBack(): void {
    const t = this._getActiveTab();
    if (!t || t.historyIndex <= 0) return;
    t.historyIndex -= 1;
    const url = t.history[t.historyIndex];
    if (t.iframe) t.iframe.src = url;
    this._updateAddressBar(url);
    this._updateNavButtons();
  }

  public goForward(): void {
    const t = this._getActiveTab();
    if (!t || t.historyIndex >= t.history.length - 1) return;
    t.historyIndex += 1;
    const url = t.history[t.historyIndex];
    if (t.iframe) t.iframe.src = url;
    this._updateAddressBar(url);
    this._updateNavButtons();
  }

  public reload(): void {
    const t = this._getActiveTab();
    if (!t || !t.iframe || !t.iframe.src || t.iframe.src === 'about:blank') return;
    t.iframe.src = t.iframe.src;
  }

  public open(): void {
    this.isOpen = true;
    if (this.container) this.container.style.display = 'flex';
    // Focus address bar if no active URL
    const t = this._getActiveTab();
    if (t && (!t.url || t.url === 'about:blank')) {
      setTimeout(() => this.addressBar?.focus(), 50);
    }
  }

  public close(): void {
    this.isOpen = false;
    if (this.container) this.container.style.display = 'none';
    this._closeAllPanels();
  }

  private _closeAllPanels(): void {
    [this.commentsPanel, this.bookmarksPanel, this.historyPanel].forEach((p) => {
      if (p) p.style.right = '-340px';
    });
  }

  private _togglePanel(panel: HTMLElement | null, renderFn?: () => void): void {
    if (!panel) return;
    const isOpen = panel.style.right === '0px';
    this._closeAllPanels();
    if (!isOpen) {
      panel.style.right = '0px';
      if (renderFn) renderFn();
    }
  }

  // ---------- Comments ----------

  public toggleComments(): void {
    this._togglePanel(this.commentsPanel, () => this._renderComments());
  }

  private _renderComments(): void {
    if (!this.commentsList) return;
    const active = this._getActiveTab();
    const activeUrl = active?.url || '';
    const list = activeUrl
      ? this.comments.filter((c) => c.url === activeUrl)
      : this.comments.slice(-50);
    this.commentsList.innerHTML = '';
    if (list.length === 0) {
      this.commentsList.innerHTML = `<div style="color: rgba(255,255,255,0.4); font-size: 12px; text-align: center; padding: 20px;">暂无评论</div>`;
      return;
    }
    list.forEach((c) => {
      const el = document.createElement('div');
      el.style.cssText = `
        background: rgba(255,255,255,0.06); border-radius: 8px;
        padding: 10px; font-size: 12px;
      `;
      el.innerHTML = `
        <div style="color: rgba(255,255,255,0.5); font-size: 10px; margin-bottom: 4px;">
          ${new Date(c.timestamp).toLocaleString()}
        </div>
        <div style="color: #fff; line-height: 1.5;">${this._escape(c.text)}</div>
        ${c.url ? `<div style="color: #6366f1; font-size: 10px; margin-top: 4px;">📍 ${this._escape(this._displayUrl(c.url))}</div>` : ''}
      `;
      this.commentsList?.appendChild(el);
    });
  }

  private _addComment(text: string): void {
    const active = this._getActiveTab();
    const comment: BrowserComment = {
      text,
      url: active?.url || '',
      timestamp: Date.now(),
      tabId: active?.id || '',
    };
    this.comments.push(comment);
    if (this.comments.length > BROWSER_LIMITS.maxComments) {
      this.comments = this.comments.slice(-BROWSER_LIMITS.maxComments);
    }
    this._saveComments();
    this._renderComments();
    if (this.onComment) this.onComment(comment);
  }

  // ---------- Bookmarks ----------

  public isBookmarked(url: string): boolean {
    return this.bookmarks.some((b) => b.url === url);
  }

  public addBookmark(url: string, title?: string): void {
    if (!url || url === 'about:blank') return;
    if (this.isBookmarked(url)) return;
    this.bookmarks.push({
      url,
      title: title || this._displayUrl(url),
      addedAt: Date.now(),
    });
    this._saveBookmarks();
    this._updateBookmarkToggle(url);
    window.showToast?.('浏览器', '已添加书签', 'success');
  }

  public removeBookmark(url: string): void {
    this.bookmarks = this.bookmarks.filter((b) => b.url !== url);
    this._saveBookmarks();
    this._updateBookmarkToggle(url);
    window.showToast?.('浏览器', '已移除书签', 'info');
  }

  public toggleBookmarkCurrent(): void {
    const t = this._getActiveTab();
    if (!t || !t.url || t.url === 'about:blank') return;
    if (this.isBookmarked(t.url)) {
      this.removeBookmark(t.url);
    } else {
      this.addBookmark(t.url, t.title);
    }
  }

  public toggleBookmarksPanel(): void {
    this._togglePanel(this.bookmarksPanel, () => this._renderBookmarks());
  }

  private _renderBookmarks(): void {
    if (!this.bookmarksList) return;
    if (this.bookmarks.length === 0) {
      this.bookmarksList.innerHTML = `<div style="color: rgba(255,255,255,0.4); font-size: 12px; text-align: center; padding: 20px;">
        <i class="fas fa-bookmark" style="font-size: 28px; opacity: 0.3; display: block; margin-bottom: 8px;"></i>
        点击地址栏星标收藏页面
      </div>`;
      return;
    }
    this.bookmarksList.innerHTML = '';
    this.bookmarks.forEach((b) => {
      const el = document.createElement('div');
      el.style.cssText = `
        display: flex; align-items: center; gap: 8px;
        padding: 8px 10px; border-radius: 6px;
        background: rgba(255,255,255,0.04);
        cursor: pointer; transition: background 0.15s;
      `;
      el.innerHTML = `
        <i class="fas fa-star" style="color: #FF9500; font-size: 11px;"></i>
        <div style="flex: 1; overflow: hidden;">
          <div style="color: #fff; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${this._escape(b.title)}</div>
          <div style="color: rgba(255,255,255,0.4); font-size: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${this._escape(b.url)}</div>
        </div>
        <i class="fas fa-times bm-remove" style="color: rgba(255,255,255,0.3); font-size: 10px; padding: 2px;"></i>
      `;
      el.addEventListener('mouseenter', () => (el.style.background = 'rgba(255,255,255,0.08)'));
      el.addEventListener('mouseleave', () => (el.style.background = 'rgba(255,255,255,0.04)'));
      el.addEventListener('click', (e) => {
        const target = e.target as HTMLElement;
        if (target.classList.contains('bm-remove') || target.closest('.bm-remove')) {
          this.removeBookmark(b.url);
          this._renderBookmarks();
        } else {
          this.navigate(b.url);
          this._closeAllPanels();
        }
      });
      this.bookmarksList?.appendChild(el);
    });
  }

  // ---------- History ----------

  public toggleHistoryPanel(): void {
    this._togglePanel(this.historyPanel, () => this._renderHistory(this.historySearchInput?.value || ''));
  }

  private _recordHistory(url: string, title: string, tabId: string): void {
    if (!url || url === 'about:blank') return;
    // Deduplicate consecutive entries for the same URL
    const last = this.historyEntries[this.historyEntries.length - 1];
    if (last && last.url === url) {
      last.title = title || last.title;
      last.visitedAt = Date.now();
    } else {
      this.historyEntries.push({ url, title, visitedAt: Date.now(), tabId });
      if (this.historyEntries.length > BROWSER_LIMITS.maxGlobalHistory) {
        this.historyEntries = this.historyEntries.slice(-BROWSER_LIMITS.maxGlobalHistory);
      }
    }
    this._saveHistory();
    // If history panel is open, refresh it
    if (this.historyPanel && this.historyPanel.style.right === '0px') {
      this._renderHistory(this.historySearchInput?.value || '');
    }
  }

  private _renderHistory(query: string = ''): void {
    if (!this.historyList) return;
    const q = query.trim().toLowerCase();
    const list = q
      ? this.historyEntries.filter(
          (h) => h.url.toLowerCase().includes(q) || (h.title || '').toLowerCase().includes(q)
        )
      : this.historyEntries.slice().reverse();

    if (list.length === 0) {
      this.historyList.innerHTML = `<div style="color: rgba(255,255,255,0.4); font-size: 12px; text-align: center; padding: 20px;">
        <i class="fas fa-history" style="font-size: 28px; opacity: 0.3; display: block; margin-bottom: 8px;"></i>
        ${q ? '无匹配历史记录' : '暂无历史记录'}
      </div>`;
      return;
    }

    this.historyList.innerHTML = '';
    list.forEach((h) => {
      const el = document.createElement('div');
      el.style.cssText = `
        display: flex; flex-direction: column; gap: 2px;
        padding: 8px 10px; border-radius: 6px;
        background: rgba(255,255,255,0.04); cursor: pointer;
        transition: background 0.15s;
      `;
      el.innerHTML = `
        <div style="color: #fff; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${this._escape(h.title || h.url)}</div>
        <div style="color: rgba(255,255,255,0.4); font-size: 10px; display: flex; justify-content: space-between; gap: 8px;">
          <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${this._escape(h.url)}</span>
          <span style="flex-shrink: 0;">${new Date(h.visitedAt).toLocaleString()}</span>
        </div>
      `;
      el.addEventListener('mouseenter', () => (el.style.background = 'rgba(255,255,255,0.08)'));
      el.addEventListener('mouseleave', () => (el.style.background = 'rgba(255,255,255,0.04)'));
      el.addEventListener('click', () => {
        this.navigate(h.url);
        this._closeAllPanels();
      });
      this.historyList?.appendChild(el);
    });
  }

  public clearHistory(): void {
    if (!confirm('确定清空全部历史记录吗？此操作不可撤销。')) return;
    this.historyEntries = [];
    this._saveHistory();
    this._renderHistory(this.historySearchInput?.value || '');
    window.showToast?.('浏览器', '历史记录已清空', 'info');
  }

  // ---------- Per-tab history bookkeeping ----------

  private _updateTabHistory(tab: BrowserTab, url: string): void {
    if (url === 'about:blank') return;
    // Trim forward history when navigating from a back-state
    tab.history = tab.history.slice(0, tab.historyIndex + 1);
    // Avoid duplicate consecutive entries
    if (tab.history[tab.history.length - 1] !== url) {
      tab.history.push(url);
    }
    tab.historyIndex = tab.history.length - 1;
    if (tab.history.length > BROWSER_LIMITS.maxHistoryPerTab) {
      const shift = tab.history.length - BROWSER_LIMITS.maxHistoryPerTab;
      tab.history = tab.history.slice(shift);
      tab.historyIndex -= shift;
    }
    this._updateNavButtons();
  }

  // ---------- Site filtering (existing API) ----------

  public blockSite(domain: string): void {
    if (!this.blockedSites.includes(domain)) {
      this.blockedSites.push(domain);
      this._saveSettings();
    }
  }

  public unblockSite(domain: string): void {
    this.blockedSites = this.blockedSites.filter((s) => s !== domain);
    this._saveSettings();
  }

  public allowSite(domain: string): void {
    if (!this.allowedSites.includes(domain)) {
      this.allowedSites.push(domain);
      this._saveSettings();
    }
  }

  public disallowSite(domain: string): void {
    this.allowedSites = this.allowedSites.filter((s) => s !== domain);
    this._saveSettings();
  }

  // ---------- Misc accessors (existing API) ----------

  public getNetworkLogs(): any[] {
    return this._networkLogs || [];
  }

  public getConsoleLogs(): any[] {
    return this._consoleLogs || [];
  }

  /**
   * Capture the active tab's page metadata + first 1000 chars of body text.
   * Returns crossOrigin=true when the iframe cannot be inspected (e.g. https
   * page inside the file://-origin Butler shell).
   */
  public capturePage(): any {
    const tab = this._getActiveTab();
    if (!tab || !tab.iframe) {
      return { title: '', url: '', meta: {}, bodyText: '' };
    }
    try {
      const doc = tab.iframe.contentDocument || tab.iframe.contentWindow?.document;
      if (doc) {
        return {
          title: doc.title || '',
          url: tab.iframe.src,
          meta: {
            description: doc.querySelector('meta[name="description"]')?.getAttribute('content') || '',
            keywords: doc.querySelector('meta[name="keywords"]')?.getAttribute('content') || '',
          },
          bodyText: doc.body?.innerText?.substring(0, 1000) || '',
        };
      }
    } catch (e: any) {
      console.warn('无法访问 iframe 内容（可能跨域）:', e.message);
    }
    return {
      title: tab.title || '',
      url: tab.iframe.src || '',
      meta: {},
      bodyText: '',
      crossOrigin: true,
    };
  }

  public destroy(): void {
    this.close();
    if (this.container) {
      this.container.innerHTML = '';
    }
    this.tabs = [];
    this.activeTabId = null;
    this.container = null;
  }

  // ---------- Helpers ----------

  private _displayUrl(url: string): string {
    if (!url || url === 'about:blank') return '';
    try {
      const u = new URL(url);
      const path = u.pathname && u.pathname !== '/' ? u.pathname : '';
      const search = u.search ? u.search : '';
      const display = `${u.host}${path}${search}`;
      return display.length > 60 ? display.substring(0, 60) + '…' : display;
    } catch {
      return url.length > 60 ? url.substring(0, 60) + '…' : url;
    }
  }

  private _escape(s: any): string {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

if (typeof window !== 'undefined') {
  (window as any).InAppBrowser = InAppBrowser;
  (window as any).butlerBrowser = null;
  (window as any).initBrowser = function (containerId: string = 'browser-container') {
    if ((window as any).butlerBrowser) {
      (window as any).butlerBrowser.destroy();
    }
    (window as any).butlerBrowser = new InAppBrowser(containerId);
    return (window as any).butlerBrowser;
  };
}
