/**
 * Butler Media Preview — 图片与视频预览组件
 * 点击缩略图弹出全屏预览，支持缩放、拖拽、旋转、左右切换
 */

interface MediaPreviewItem {
  type: 'image' | 'video';
  src: string;
  thumbnail?: string;
  title?: string;
  poster?: string;
}

interface MediaPreviewOptions {
  /** 预览项目列表 */
  items: MediaPreviewItem[];
  /** 初始显示第几张 */
  initialIndex?: number;
  /** 背景遮罩透明度 */
  backdropOpacity?: number;
  /** 是否显示缩略图栏 */
  showThumbnails?: boolean;
  /** 是否循环切换 */
  loop?: boolean;
  /** 关闭回调 */
  onClose?: () => void;
}

class MediaPreview {
  private overlay: HTMLElement | null = null;
  private container: HTMLElement | null = null;
  private mediaEl: HTMLElement | null = null;
  private thumbnailsBar: HTMLElement | null = null;

  private items: MediaPreviewItem[] = [];
  private currentIndex = 0;
  private isOpen = false;

  // 缩放 & 拖拽状态
  private scale = 1;
  private rotate = 0;
  private translateX = 0;
  private translateY = 0;
  private isDragging = false;
  private dragStartX = 0;
  private dragStartY = 0;

  // 配置
  private backdropOpacity = 0.85;
  private showThumbnails = true;
  private loop = true;
  private onClose: (() => void) | null = null;

  constructor(options: MediaPreviewOptions) {
    this.items = options.items;
    this.currentIndex = options.initialIndex ?? 0;
    this.backdropOpacity = options.backdropOpacity ?? 0.85;
    this.showThumbnails = options.showThumbnails ?? true;
    this.loop = options.loop ?? true;
    this.onClose = options.onClose ?? null;
  }

  /** 打开预览 */
  open(index?: number): void {
    if (this.isOpen) return;
    if (index !== undefined) this.currentIndex = index;
    this.isOpen = true;

    this.injectStyles();
    this.createOverlay();
    this.renderMedia();
    if (this.showThumbnails && this.items.length > 1) {
      this.createThumbnails();
    }
    this.bindKeys();
    document.body.style.overflow = 'hidden';
  }

  /** 关闭预览 */
  close(): void {
    if (!this.isOpen) return;
    this.isOpen = false;

    this.overlay?.remove();
    this.overlay = null;
    this.container = null;
    this.mediaEl = null;
    this.thumbnailsBar = null;

    this.unbindKeys();
    document.body.style.overflow = '';
    this.onClose?.();
  }

  /** 下一张 */
  next(): void {
    if (this.currentIndex < this.items.length - 1) {
      this.currentIndex++;
    } else if (this.loop) {
      this.currentIndex = 0;
    } else {
      return;
    }
    this.resetTransform();
    this.renderMedia();
    this.updateThumbnails();
  }

  /** 上一张 */
  prev(): void {
    if (this.currentIndex > 0) {
      this.currentIndex--;
    } else if (this.loop) {
      this.currentIndex = this.items.length - 1;
    } else {
      return;
    }
    this.resetTransform();
    this.renderMedia();
    this.updateThumbnails();
  }

  /** 放大 */
  zoomIn(): void {
    this.scale = Math.min(this.scale * 1.3, 10);
    this.applyTransform();
  }

  /** 缩小 */
  zoomOut(): void {
    this.scale = Math.max(this.scale / 1.3, 0.1);
    this.applyTransform();
  }

  /** 重置缩放和旋转 */
  resetTransform(): void {
    this.scale = 1;
    this.rotate = 0;
    this.translateX = 0;
    this.translateY = 0;
    this.applyTransform();
  }

  /** 旋转 */
  rotateRight(): void {
    this.rotate = (this.rotate + 90) % 360;
    this.applyTransform();
  }

  /** 适应屏幕 */
  fitToScreen(): void {
    this.resetTransform();
  }

  // ---------- 私有方法 ----------

  private createOverlay(): void {
    this.overlay = document.createElement('div');
    this.overlay.className = 'butler-media-preview-overlay';
    this.overlay.style.cssText = `
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      z-index: 999999;
      background: rgba(0, 0, 0, ${this.backdropOpacity});
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      animation: bmp-fadeIn 0.2s ease;
    `;

    // 顶部工具栏
    const toolbar = document.createElement('div');
    toolbar.className = 'butler-media-preview-toolbar';
    toolbar.style.cssText = `
      position: absolute;
      top: 0; left: 0; right: 0;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 20px;
      background: linear-gradient(180deg, rgba(0,0,0,0.6) 0%, transparent 100%);
      z-index: 10;
      user-select: none;
    `;

    // 左侧：标题
    const titleEl = document.createElement('span');
    titleEl.className = 'bmp-title';
    titleEl.style.cssText = `color: #fff; font-size: 14px; font-family: -apple-system, sans-serif;`;
    titleEl.textContent = this.items[this.currentIndex]?.title || '';

    // 右侧：操作按钮
    const actions = document.createElement('div');
    actions.style.cssText = `display: flex; gap: 8px; align-items: center;`;

    const buttons: Array<{ icon: string; title: string; action: () => void }> = [
      { icon: '🔍−', title: '缩小', action: () => this.zoomOut() },
      { icon: '🔍+', title: '放大', action: () => this.zoomIn() },
      { icon: '↻', title: '旋转', action: () => this.rotateRight() },
      { icon: '⊞', title: '适应屏幕', action: () => this.fitToScreen() },
      { icon: '✕', title: '关闭 (Esc)', action: () => this.close() },
    ];

    for (const btn of buttons) {
      const el = document.createElement('button');
      el.textContent = btn.icon;
      el.title = btn.title;
      el.style.cssText = `
        background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.2);
        color: #fff;
        width: 36px; height: 36px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background 0.15s;
      `;
      el.addEventListener('mouseenter', () => { el.style.background = 'rgba(255,255,255,0.3)'; });
      el.addEventListener('mouseleave', () => { el.style.background = 'rgba(255,255,255,0.15)'; });
      el.addEventListener('click', (e) => { e.stopPropagation(); btn.action(); });
      actions.appendChild(el);
    }

    toolbar.appendChild(titleEl);
    toolbar.appendChild(actions);

    // 中间：媒体容器
    this.container = document.createElement('div');
    this.container.className = 'butler-media-preview-container';
    this.container.style.cssText = `
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      overflow: hidden;
      cursor: grab;
      user-select: none;
    `;

    // 左右切换箭头
    if (this.items.length > 1) {
      const prevBtn = this.createArrowButton('‹', () => this.prev());
      prevBtn.style.cssText += `position: absolute; left: 16px; top: 50%; transform: translateY(-50%); z-index: 10;`;
      this.overlay.appendChild(prevBtn);

      const nextBtn = this.createArrowButton('›', () => this.next());
      nextBtn.style.cssText += `position: absolute; right: 16px; top: 50%; transform: translateY(-50%); z-index: 10;`;
      this.overlay.appendChild(nextBtn);
    }

    // 底部计数器
    const counter = document.createElement('div');
    counter.className = 'bmp-counter';
    counter.style.cssText = `
      position: absolute;
      bottom: 80px;
      left: 50%;
      transform: translateX(-50%);
      color: rgba(255,255,255,0.8);
      font-size: 13px;
      font-family: -apple-system, sans-serif;
      background: rgba(0,0,0,0.4);
      padding: 4px 12px;
      border-radius: 12px;
      z-index: 10;
    `;
    counter.textContent = `${this.currentIndex + 1} / ${this.items.length}`;

    this.overlay.appendChild(toolbar);
    this.overlay.appendChild(this.container);
    this.overlay.appendChild(counter);

    // 点击遮罩关闭
    this.overlay.addEventListener('click', (e) => {
      if (e.target === this.container || e.target === this.overlay) {
        this.close();
      }
    });

    // 拖拽
    this.container.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      this.isDragging = true;
      this.dragStartX = e.clientX - this.translateX;
      this.dragStartY = e.clientY - this.translateY;
      this.container!.style.cursor = 'grabbing';
    });

    document.addEventListener('mousemove', this._onDragMove);
    document.addEventListener('mouseup', this._onDragEnd);

    // 滚轮缩放
    this.container.addEventListener('wheel', (e) => {
      e.preventDefault();
      if (e.deltaY < 0) {
        this.zoomIn();
      } else {
        this.zoomOut();
      }
    });

    document.body.appendChild(this.overlay);
  }

  private _onDragMove = (e: MouseEvent) => {
    if (!this.isDragging || !this.container) return;
    this.translateX = e.clientX - this.dragStartX;
    this.translateY = e.clientY - this.dragStartY;
    this.applyTransform();
  };

  private _onDragEnd = () => {
    this.isDragging = false;
    if (this.container) this.container.style.cursor = 'grab';
  };

  private createArrowButton(text: string, onClick: () => void): HTMLElement {
    const btn = document.createElement('button');
    btn.textContent = text;
    btn.style.cssText = `
      background: rgba(0,0,0,0.4);
      border: 1px solid rgba(255,255,255,0.2);
      color: #fff;
      width: 48px; height: 48px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s;
      backdrop-filter: blur(4px);
    `;
    btn.addEventListener('mouseenter', () => { btn.style.background = 'rgba(255,255,255,0.2)'; });
    btn.addEventListener('mouseleave', () => { btn.style.background = 'rgba(0,0,0,0.4)'; });
    btn.addEventListener('click', (e) => { e.stopPropagation(); onClick(); });
    return btn;
  }

  private renderMedia(): void {
    if (!this.container) return;
    this.container.innerHTML = '';

    const item = this.items[this.currentIndex];
    if (!item) return;

    // 更新标题和计数
    const title = this.overlay?.querySelector('.bmp-title');
    if (title) title.textContent = item.title || '';
    const counter = this.overlay?.querySelector('.bmp-counter');
    if (counter) counter.textContent = `${this.currentIndex + 1} / ${this.items.length}`;

    if (item.type === 'image') {
      const img = document.createElement('img');
      img.src = item.src;
      img.style.cssText = `
        max-width: 90vw;
        max-height: 85vh;
        object-fit: contain;
        border-radius: 4px;
        box-shadow: 0 8px 40px rgba(0,0,0,0.4);
        transition: transform 0.2s ease;
        user-select: none;
        -webkit-user-drag: none;
      `;
      img.draggable = false;
      this.mediaEl = img;
      this.container.appendChild(img);
      this.applyTransform();
    }

    if (item.type === 'video') {
      const video = document.createElement('video');
      video.src = item.src;
      video.controls = true;
      video.autoplay = true;
      video.playsInline = true;
      if (item.poster) video.poster = item.poster;
      video.style.cssText = `
        max-width: 90vw;
        max-height: 85vh;
        object-fit: contain;
        border-radius: 4px;
        box-shadow: 0 8px 40px rgba(0,0,0,0.4);
        background: #000;
      `;
      this.mediaEl = video;
      this.container.appendChild(video);
    }
  }

  private applyTransform(): void {
    if (!this.mediaEl) return;
    (this.mediaEl as HTMLElement).style.transform =
      `translate(${this.translateX}px, ${this.translateY}px) scale(${this.scale}) rotate(${this.rotate}deg)`;
  }

  private createThumbnails(): void {
    this.thumbnailsBar = document.createElement('div');
    this.thumbnailsBar.style.cssText = `
      position: absolute;
      bottom: 0; left: 0; right: 0;
      display: flex;
      justify-content: center;
      gap: 6px;
      padding: 12px 20px;
      background: linear-gradient(0deg, rgba(0,0,0,0.6) 0%, transparent 100%);
      z-index: 10;
      overflow-x: auto;
      user-select: none;
    `;

    this.items.forEach((item, idx) => {
      const thumb = document.createElement('div');
      thumb.style.cssText = `
        width: 48px; height: 48px;
        border-radius: 6px;
        overflow: hidden;
        cursor: pointer;
        border: 2px solid ${idx === this.currentIndex ? '#4a9eff' : 'transparent'};
        transition: border-color 0.15s, transform 0.15s;
        flex-shrink: 0;
        opacity: ${idx === this.currentIndex ? '1' : '0.6'};
      `;

      if (item.type === 'image') {
        const img = document.createElement('img');
        img.src = item.thumbnail || item.src;
        img.style.cssText = `width: 100%; height: 100%; object-fit: cover;`;
        thumb.appendChild(img);
      } else {
        thumb.style.cssText += `background: #222; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 18px;`;
        thumb.textContent = '▶';
      }

      thumb.addEventListener('click', () => {
        this.currentIndex = idx;
        this.resetTransform();
        this.renderMedia();
        this.updateThumbnails();
      });
      thumb.addEventListener('mouseenter', () => { thumb.style.transform = 'scale(1.1)'; });
      thumb.addEventListener('mouseleave', () => { thumb.style.transform = 'scale(1)'; });

      this.thumbnailsBar!.appendChild(thumb);
    });

    this.overlay?.appendChild(this.thumbnailsBar);
  }

  private updateThumbnails(): void {
    if (!this.thumbnailsBar) return;
    const thumbs = this.thumbnailsBar.children;
    for (let i = 0; i < thumbs.length; i++) {
      const el = thumbs[i] as HTMLElement;
      el.style.borderColor = i === this.currentIndex ? '#4a9eff' : 'transparent';
      el.style.opacity = i === this.currentIndex ? '1' : '0.6';
    }
  }

  // ---------- 快捷键 ----------

  private _keyHandler = (e: KeyboardEvent) => {
    if (!this.isOpen) return;
    switch (e.key) {
      case 'Escape': this.close(); break;
      case 'ArrowLeft': this.prev(); break;
      case 'ArrowRight': this.next(); break;
      case 'ArrowUp':
      case '+': case '=': this.zoomIn(); break;
      case 'ArrowDown':
      case '-': this.zoomOut(); break;
      case '0': this.fitToScreen(); break;
      case 'r': this.rotateRight(); break;
    }
  };

  private bindKeys(): void {
    document.addEventListener('keydown', this._keyHandler);
  }

  private unbindKeys(): void {
    document.removeEventListener('keydown', this._keyHandler);
    document.removeEventListener('mousemove', this._onDragMove);
    document.removeEventListener('mouseup', this._onDragEnd);
  }

  // ---------- 样式注入 ----------

  private static stylesInjected = false;

  private injectStyles(): void {
    if (MediaPreview.stylesInjected) return;
    MediaPreview.stylesInjected = true;

    const style = document.createElement('style');
    style.textContent = `
      @keyframes bmp-fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
      }
    `;
    document.head.appendChild(style);
  }
}

// ============================================================
// 便捷 API
// ============================================================

let _instance: MediaPreview | null = null;

/**
 * 打开图片/视频预览
 *
 * @example
 * // 单张图片
 * window.previewMedia({ type: 'image', src: 'https://...' });
 *
 * @example
 * // 多张图片
 * window.previewMedia([
 *   { type: 'image', src: 'a.png', title: '图1' },
 *   { type: 'image', src: 'b.png', title: '图2' },
 *   { type: 'video', src: 'c.mp4', title: '视频' },
 * ], { initialIndex: 0 });
 */
function previewMedia(
  input: MediaPreviewItem | MediaPreviewItem[],
  options?: Partial<MediaPreviewOptions>
): void {
  const items = Array.isArray(input) ? input : [input];
  _instance?.close();
  _instance = new MediaPreview({ items, ...options });
  _instance.open(options?.initialIndex);
}

/** 关闭当前预览 */
function closeMediaPreview(): void {
  _instance?.close();
  _instance = null;
}

export { MediaPreview, previewMedia, closeMediaPreview };
export type { MediaPreviewItem, MediaPreviewOptions };
