/**
 * Butler In-App Browser Component in TypeScript
 */

interface BrowserComment {
  text: string;
  url: string;
  timestamp: number;
}

interface BrowserSettings {
  blockedSites: string[];
  allowedSites: string[];
}

class InAppBrowser {
  public containerId: string;
  public container: HTMLElement | null = null;
  public iframe: HTMLIFrameElement | null = null;
  public placeholder: HTMLElement | null = null;
  public addressBar: HTMLInputElement | null = null;
  public backBtn: HTMLElement | null = null;
  public forwardBtn: HTMLElement | null = null;
  public refreshBtn: HTMLElement | null = null;
  public commentBtn: HTMLElement | null = null;
  public closeBtn: HTMLElement | null = null;
  public statusUrl: HTMLElement | null = null;
  public commentsPanel: HTMLElement | null = null;
  public commentsList: HTMLElement | null = null;
  public commentInput: HTMLTextAreaElement | null = null;
  public commentSubmit: HTMLElement | null = null;
  public commentsClose: HTMLElement | null = null;

  public comments: BrowserComment[] = [];
  public history: string[] = [];
  public historyIndex: number = -1;
  public blockedSites: string[] = [];
  public allowedSites: string[] = [];
  public isOpen: boolean = false;

  public onComment: ((comment: BrowserComment) => void) | null = null;
  public onPageLoad: ((url: string) => void) | null = null;
  public onError: ((err: string) => void) | null = null;

  private _networkLogs: any[] = [];
  private _consoleLogs: any[] = [];

  constructor(containerId: string) {
    this.containerId = containerId;
    this._loadSettings();
    this._buildUI();
  }

  private _loadSettings(): void {
    try {
      const settings = localStorage.getItem('butler_browser_settings');
      if (settings) {
        const parsed: BrowserSettings = JSON.parse(settings);
        this.blockedSites = parsed.blockedSites || [];
        this.allowedSites = parsed.allowedSites || [];
      }
    } catch (e) {
      console.warn('浏览器设置加载失败:', e);
    }
  }

  private _saveSettings(): void {
    try {
      localStorage.setItem(
        'butler_browser_settings',
        JSON.stringify({
          blockedSites: this.blockedSites,
          allowedSites: this.allowedSites,
        })
      );
    } catch (e) {
      console.warn('浏览器设置保存失败:', e);
    }
  }

  private _buildUI(): void {
    this.container = document.getElementById(this.containerId);
    if (!this.container) return;

    this.container.innerHTML = `
      <div class="butler-browser" style="
          position: absolute;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(20, 20, 30, 0.98);
          border-radius: 12px;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          z-index: 10000;
          box-shadow: 0 20px 60px rgba(0,0,0,0.4);
      ">
        <div class="browser-toolbar" style="
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 14px;
            background: linear-gradient(180deg, #2a2a3a 0%, #1e1e2e 100%);
            border-bottom: 1px solid rgba(255,255,255,0.1);
        ">
          <button class="browser-btn browser-back" title="后退" style="${this._btnStyle()}">
            <i class="fas fa-chevron-left"></i>
          </button>
          <button class="browser-btn browser-forward" title="前进" style="${this._btnStyle()}">
            <i class="fas fa-chevron-right"></i>
          </button>
          <button class="browser-btn browser-refresh" title="刷新" style="${this._btnStyle()}">
            <i class="fas fa-sync-alt"></i>
          </button>
          <div class="browser-address-container" style="
              flex: 1;
              display: flex;
              align-items: center;
              background: rgba(255,255,255,0.08);
              border-radius: 8px;
              padding: 4px 12px;
              gap: 8px;
          ">
            <i class="fas fa-lock" style="color: #34C759; font-size: 11px;"></i>
            <input type="text" class="browser-address" placeholder="输入 URL 或搜索..."
                style="flex: 1; background: transparent; border: none; outline: none;
                color: #fff; font-size: 13px; font-family: inherit;" />
          </div>
          <button class="browser-btn browser-comment" title="评论页面" style="${this._btnStyle()}">
            <i class="fas fa-comment-dots"></i>
          </button>
          <button class="browser-btn browser-close" title="关闭" style="${this._btnStyle()}">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="browser-content" style="flex: 1; position: relative; background: #fff;">
          <iframe class="browser-iframe" style="
              width: 100%; height: 100%; border: none;
              background: #fff;
          " sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals allow-downloads"></iframe>
          <div class="browser-placeholder" style="
              position: absolute; inset: 0;
              display: flex; flex-direction: column;
              align-items: center; justify-content: center;
              color: rgba(255,255,255,0.5);
              background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
              gap: 16px;
          ">
            <i class="fas fa-globe" style="font-size: 48px; opacity: 0.3;"></i>
            <div style="font-size: 16px;">输入 URL 开始浏览</div>
            <div style="font-size: 12px; opacity: 0.6;">支持本地开发服务器和文件预览</div>
          </div>
        </div>

        <div class="browser-status" style="
            display: flex;
            align-items: center;
            padding: 6px 14px;
            background: #1a1a28;
            border-top: 1px solid rgba(255,255,255,0.08);
            font-size: 11px;
            color: rgba(255,255,255,0.6);
            gap: 12px;
        ">
          <span class="browser-status-url"></span>
          <span class="browser-status-separator">·</span>
          <span class="browser-status-secure"><i class="fas fa-shield-alt"></i> 安全浏览</span>
        </div>

        <div class="browser-comments-panel" style="
            position: absolute;
            top: 60px; right: -320px;
            width: 300px;
            height: calc(100% - 100px);
            background: rgba(25,25,35,0.98);
            border-left: 1px solid rgba(255,255,255,0.1);
            padding: 16px;
            transition: right 0.3s ease;
            overflow-y: auto;
            z-index: 100;
        ">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-weight: 600; font-size: 14px;">页面评论</div>
            <button class="comments-close" style="background: none; border: none; color: rgba(255,255,255,0.6); cursor: pointer;">
              <i class="fas fa-times"></i>
            </button>
          </div>
          <div class="comments-list" style="display: flex; flex-direction: column; gap: 8px;"></div>
          <div class="comment-input-area" style="margin-top: 12px;">
            <textarea class="comment-input" placeholder="添加评论..."
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
      </div>
    `;

    this.iframe = this.container.querySelector('.browser-iframe');
    this.placeholder = this.container.querySelector('.browser-placeholder');
    this.addressBar = this.container.querySelector('.browser-address');
    this.backBtn = this.container.querySelector('.browser-back');
    this.forwardBtn = this.container.querySelector('.browser-forward');
    this.refreshBtn = this.container.querySelector('.browser-refresh');
    this.commentBtn = this.container.querySelector('.browser-comment');
    this.closeBtn = this.container.querySelector('.browser-close');
    this.statusUrl = this.container.querySelector('.browser-status-url');
    this.commentsPanel = this.container.querySelector('.browser-comments-panel');
    this.commentsList = this.container.querySelector('.comments-list');
    this.commentInput = this.container.querySelector('.comment-input');
    this.commentSubmit = this.container.querySelector('.comment-submit');
    this.commentsClose = this.container.querySelector('.comments-close');

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
    this.backBtn?.addEventListener('click', () => this.goBack());
    this.forwardBtn?.addEventListener('click', () => this.goForward());
    this.refreshBtn?.addEventListener('click', () => this.reload());
    this.closeBtn?.addEventListener('click', () => this.close());
    this.commentBtn?.addEventListener('click', () => this.toggleComments());
    this.commentsClose?.addEventListener('click', () => this.toggleComments());

    this.addressBar?.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Enter') {
        this.navigate((e.target as HTMLInputElement).value);
      }
    });

    this.commentSubmit?.addEventListener('click', () => {
      const text = this.commentInput?.value.trim() || '';
      if (text) {
        this._addComment(text);
        if (this.commentInput) this.commentInput.value = '';
      }
    });

    this.iframe?.addEventListener('load', () => {
      if (!this.iframe) return;
      const url = this.iframe.src;
      if (this.statusUrl) this.statusUrl.textContent = this._displayUrl(url);
      this._updateHistory(url);
      if (this.onPageLoad) this.onPageLoad(url);
    });

    this.iframe?.addEventListener('error', () => {
      console.warn('iframe 加载出错');
    });

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

  private _displayUrl(url: string): string {
    if (!url || url === 'about:blank') return '';
    try {
      const u = new URL(url);
      return `${u.host}${u.pathname !== '/' ? u.pathname : ''}`;
    } catch {
      return url.length > 50 ? url.substring(0, 50) + '...' : url;
    }
  }

  public navigate(url: string): void {
    if (!url) return;

    let finalUrl = url.trim();
    if (!finalUrl.match(/^(https?:\/\/|file:\/\/)/)) {
      finalUrl = 'https://' + finalUrl;
    }

    if (!this._isUrlAllowed(finalUrl)) {
      console.warn(`网站被屏蔽: ${finalUrl}`);
      if (this.onError) this.onError(`该网站已被屏蔽: ${finalUrl}`);
      return;
    }

    if (this.placeholder) this.placeholder.style.display = 'none';
    if (this.iframe) this.iframe.src = finalUrl;
    if (this.addressBar) this.addressBar.value = finalUrl;
  }

  public goBack(): void {
    if (this.historyIndex > 0) {
      this.historyIndex--;
      const url = this.history[this.historyIndex];
      if (this.iframe) this.iframe.src = url;
      if (this.addressBar) this.addressBar.value = url;
    }
  }

  public goForward(): void {
    if (this.historyIndex < this.history.length - 1) {
      this.historyIndex++;
      const url = this.history[this.historyIndex];
      if (this.iframe) this.iframe.src = url;
      if (this.addressBar) this.addressBar.value = url;
    }
  }

  public reload(): void {
    if (this.iframe && this.iframe.src && this.iframe.src !== 'about:blank') {
      this.iframe.src = this.iframe.src;
    }
  }

  public close(): void {
    this.isOpen = false;
    if (this.container) {
      this.container.style.display = 'none';
    }
  }

  public open(): void {
    this.isOpen = true;
    if (this.container) {
      this.container.style.display = 'flex';
    }
  }

  public toggleComments(): void {
    if (!this.commentsPanel) return;
    const isHidden = this.commentsPanel.style.right === '-320px' || !this.commentsPanel.style.right;
    if (isHidden) {
      this.commentsPanel.style.right = '0';
      this._renderComments();
    } else {
      this.commentsPanel.style.right = '-320px';
    }
  }

  private _renderComments(): void {
    if (!this.commentsList) return;
    this.commentsList.innerHTML = '';
    this.comments.forEach((c) => {
      const el = document.createElement('div');
      el.style.cssText = `
        background: rgba(255,255,255,0.06);
        border-radius: 8px;
        padding: 10px;
        font-size: 12px;
      `;
      el.innerHTML = `
        <div style="color: rgba(255,255,255,0.5); font-size: 10px; margin-bottom: 4px;">
          ${new Date(c.timestamp).toLocaleString()}
        </div>
        <div style="color: #fff; line-height: 1.5;">${c.text}</div>
        ${c.url ? `<div style="color: #6366f1; font-size: 10px; margin-top: 4px;">📍 ${c.url}</div>` : ''}
      `;
      this.commentsList?.appendChild(el);
    });
  }

  private _addComment(text: string): void {
    const comment: BrowserComment = {
      text,
      url: this.iframe?.src || '',
      timestamp: Date.now(),
    };
    this.comments.push(comment);
    this._renderComments();
    if (this.onComment) this.onComment(comment);
  }

  private _isUrlAllowed(url: string): boolean {
    if (this.blockedSites.some((site) => url.includes(site))) {
      return false;
    }
    if (this.allowedSites.length > 0) {
      return this.allowedSites.some((site) => url.includes(site));
    }
    return true;
  }

  private _updateHistory(url: string): void {
    if (url === 'about:blank') return;
    this.history = this.history.slice(0, this.historyIndex + 1);
    this.history.push(url);
    this.historyIndex = this.history.length - 1;

    if (this.history.length > 50) {
      this.history.shift();
      this.historyIndex--;
    }
  }

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

  public getNetworkLogs(): any[] {
    return this._networkLogs || [];
  }

  public getConsoleLogs(): any[] {
    return this._consoleLogs || [];
  }

  public capturePage(): any {
    try {
      if (!this.iframe) return { title: '', url: '', meta: {}, bodyText: '' };
      const doc = this.iframe.contentDocument || this.iframe.contentWindow?.document;
      if (doc) {
        return {
          title: doc.title || '',
          url: this.iframe.src,
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
      title: '',
      url: this.iframe?.src || '',
      meta: {},
      bodyText: '',
      crossOrigin: true,
    };
  }

  public destroy(): void {
    this.close();
    if (this.container) {
      this.container.remove();
    }
    this.container = null;
    this.iframe = null;
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
