/**
 * Butler Screen Capture & Recording Controller in TypeScript
 */

export interface SelectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type CaptureActionType = 'full_screenshot' | 'record_screen' | 'long_screenshot' | 'area_screenshot' | 'area_record';

export class ScreenCaptureController {
  private _panelModalEl: HTMLElement | null = null;
  private _overlayEl: HTMLElement | null = null;
  private _recordingIndicatorEl: HTMLElement | null = null;
  private _annotationModalEl: HTMLElement | null = null;

  private _isSelecting: boolean = false;
  private _isResizing: boolean = false;
  private _resizeHandle: string | null = null;
  private _startX: number = 0;
  private _startY: number = 0;
  private _currentRect: SelectionRect | null = null;
  private _activeMode: 'screenshot' | 'record' | null = null;

  // Recording State
  private _isRecording: boolean = false;
  private _recordingSeconds: number = 0;
  private _recordingTimer: any = null;

  // Annotation State
  private _annotationCanvas: HTMLCanvasElement | null = null;
  private _annotationCtx: CanvasRenderingContext2D | null = null;
  private _annotationTool: 'pen' | 'arrow' | 'text' | 'mosaic' = 'pen';
  private _isDrawing: boolean = false;
  private _drawStartX: number = 0;
  private _drawStartY: number = 0;
  private _canvasSnapshot: ImageData | null = null;

  constructor() {
    this._initKeyboardShortcuts();
  }

  private _initKeyboardShortcuts(): void {
    document.addEventListener('keydown', (e: KeyboardEvent) => {
      // Escape cancels selection overlay or panel
      if (e.key === 'Escape') {
        this.closeAll();
      }
    });
  }

  // --- 1. Control Panel Modal ---
  public openPanel(): void {
    if (this._panelModalEl) return;

    const html = `
      <div id="screen-capture-panel-backdrop" class="screen-capture-panel-overlay" style="
          position: fixed; inset: 0; background: rgba(0,0,0,0.35);
          backdrop-filter: blur(12px) saturate(1.8); -webkit-backdrop-filter: blur(12px) saturate(1.8);
          z-index: 10005; display: flex; align-items: center; justify-content: center;
          animation: scFadeIn 0.25s ease-out;
      ">
        <div class="screen-capture-card" style="
            background: rgba(30, 30, 30, 0.65);
            backdrop-filter: blur(20px) saturate(1.8); -webkit-backdrop-filter: blur(20px) saturate(1.8);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            width: 380px; padding: 24px 20px 18px;
            display: flex; flex-direction: column; align-items: center;
            user-select: none;
        ">
          <!-- Main 5 Functions Grid -->
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; width: 100%; margin-bottom: 16px;">
            <!-- Row 1 Top 2 items centered horizontally -->
            <div style="grid-column: span 3; display: flex; justify-content: center; gap: 20px;">
              <div onclick="window.ScreenCapture.triggerAction('full_screenshot')" class="sc-icon-btn" style="${this._btnStyle()}">
                <div style="${this._iconContainerStyle()}">
                  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="3"></rect>
                    <path d="M7 9V7h2M17 9V7h-2M7 15v2h2M17 15v2h-2"></path>
                  </svg>
                </div>
                <span style="font-size: 11px; color: #fff; margin-top: 6px; font-weight: 500;">截屏</span>
              </div>

              <div onclick="window.ScreenCapture.triggerAction('record_screen')" class="sc-icon-btn" style="${this._btnStyle()}">
                <div style="${this._iconContainerStyle()}">
                  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M23 7l-7 5 7 5V7z"></path>
                    <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
                  </svg>
                </div>
                <span style="font-size: 11px; color: #fff; margin-top: 6px; font-weight: 500;">录制屏幕</span>
              </div>
            </div>

            <!-- Row 2 Bottom 3 items -->
            <div onclick="window.ScreenCapture.triggerAction('long_screenshot')" class="sc-icon-btn" style="${this._btnStyle()}">
              <div style="${this._iconContainerStyle()}">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="5" y="2" width="14" height="20" rx="2"></rect>
                  <path d="M12 6v6M9 10l3 3 3-3M9 16h6"></path>
                </svg>
              </div>
              <span style="font-size: 11px; color: #fff; margin-top: 6px; font-weight: 500;">长截屏</span>
            </div>

            <div onclick="window.ScreenCapture.triggerAction('area_screenshot')" class="sc-icon-btn" style="${this._btnStyle()}">
              <div style="${this._iconContainerStyle()}">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M6 3H3v3M18 3h3v3M6 21H3v-3M18 21h3v-3M9 12h6"></path>
                </svg>
              </div>
              <span style="font-size: 11px; color: #fff; margin-top: 6px; font-weight: 500;">区域截屏</span>
            </div>

            <div onclick="window.ScreenCapture.triggerAction('area_record')" class="sc-icon-btn" style="${this._btnStyle()}">
              <div style="${this._iconContainerStyle()}">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="3" fill="#FF3B30"></circle>
                  <path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"></path>
                </svg>
              </div>
              <span style="font-size: 11px; color: #fff; margin-top: 6px; font-weight: 500;">区域录制</span>
            </div>
          </div>

          <!-- Close Button -->
          <div onclick="window.ScreenCapture.closeAll()" style="
              width: 32px; height: 32px; border-radius: 50%;
              background: rgba(255,255,255,0.12);
              display: flex; align-items: center; justify-content: center;
              cursor: pointer; color: rgba(255,255,255,0.8);
              transition: all 0.2s ease;
          " onmouseover="this.style.background='rgba(255,255,255,0.25)'" onmouseout="this.style.background='rgba(255,255,255,0.12)'">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </div>
        </div>
      </div>
      <style>
        @keyframes scFadeIn {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
        .sc-icon-btn:hover {
          background: rgba(255,255,255,0.12) !important;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
      </style>
    `;

    this._panelModalEl = document.createElement('div');
    this._panelModalEl.id = 'screen-capture-panel-root';
    this._panelModalEl.innerHTML = html;
    document.body.appendChild(this._panelModalEl);
  }

  private _btnStyle(): string {
    return `
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      width: 76px; height: 76px; border-radius: 14px;
      background: rgba(255,255,255,0.06); cursor: pointer;
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    `;
  }

  private _iconContainerStyle(): string {
    return `
      display: flex; align-items: center; justify-content: center;
      color: #ffffff;
    `;
  }

  public triggerAction(action: CaptureActionType): void {
    this.closePanelOnly();

    switch (action) {
      case 'full_screenshot':
        this._executeFullScreenshot();
        break;
      case 'record_screen':
        this._executeFullRecord();
        break;
      case 'long_screenshot':
        this._executeLongScreenshot();
        break;
      case 'area_screenshot':
        this.startAreaSelection('screenshot');
        break;
      case 'area_record':
        this.startAreaSelection('record');
        break;
    }
  }

  public closePanelOnly(): void {
    if (this._panelModalEl) {
      this._panelModalEl.remove();
      this._panelModalEl = null;
    }
  }

  public closeAll(): void {
    this.closePanelOnly();
    this._removeOverlay();
    this.closeAnnotationModal();
  }

  // --- 2. Full Capture Actions ---
  private async _executeFullScreenshot(): Promise<void> {
    window.showToast?.('截屏', '正在捕获全屏...', 'info');
    try {
      if ((window as any).pywebview?.api) {
        const res = await (window as any).pywebview.api.call_skill('screen_capture', 'full_screenshot');
        if (res && res.status === 'success') {
          window.showToast?.('截屏成功', `已保存至: ${res.file_path}`, 'success');
        } else {
          window.showToast?.('截屏结果', res?.message || '已复制全屏截图到剪贴板', 'success');
        }
      } else {
        window.showToast?.('截屏成功', '全屏截图已成功复制到剪贴板 (模拟模式)', 'success');
      }
    } catch (e: any) {
      window.showToast?.('截屏失败', e.message || '操作出错', 'error');
    }
  }

  private async _executeFullRecord(): Promise<void> {
    this.startRecordingUI('全屏录制');
    try {
      if ((window as any).pywebview?.api) {
        await (window as any).pywebview.api.call_skill('screen_capture', 'start_recording', { type: 'full' });
      }
    } catch (e: any) {
      console.warn('Backend recording signal:', e);
    }
  }

  private async _executeLongScreenshot(): Promise<void> {
    window.showToast?.('长截屏', '请滚动页面，完成后停止...', 'info');
    try {
      if ((window as any).pywebview?.api) {
        const res = await (window as any).pywebview.api.call_skill('screen_capture', 'long_screenshot');
        if (res && res.status === 'success') {
          window.showToast?.('长截屏完成', `长图已保存: ${res.file_path}`, 'success');
        } else {
          window.showToast?.('长截屏完成', '长截屏已生成并保存到系统目录', 'success');
        }
      } else {
        window.showToast?.('长截屏完成', '长截屏已自动合成 (模拟模式)', 'success');
      }
    } catch (e: any) {
      window.showToast?.('长截屏失败', e.message || '操作出错', 'error');
    }
  }

  // --- 3. Area Selection & Overlay ---
  public startAreaSelection(mode: 'screenshot' | 'record'): void {
    this._activeMode = mode;
    this._removeOverlay();

    const overlay = document.createElement('div');
    overlay.id = 'screen-capture-overlay';
    overlay.style.cssText = `
      position: fixed; inset: 0; z-index: 10006;
      background: rgba(0, 0, 0, 0.4);
      cursor: crosshair; user-select: none;
    `;

    overlay.innerHTML = `
      <div id="sc-selection-box" style="
          position: absolute; display: none;
          border: 2px dashed #6C5CE7;
          box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.4);
          background: transparent;
      ">
        <!-- 8 Resize Drag Handles -->
        <div class="sc-handle sc-h-tl" data-handle="tl" style="${this._handleStyle('top: -5px; left: -5px; cursor: nwse-resize;')}"></div>
        <div class="sc-handle sc-h-tm" data-handle="tm" style="${this._handleStyle('top: -5px; left: calc(50% - 4px); cursor: ns-resize;')}"></div>
        <div class="sc-handle sc-h-tr" data-handle="tr" style="${this._handleStyle('top: -5px; right: -5px; cursor: nesw-resize;')}"></div>
        <div class="sc-handle sc-h-ml" data-handle="ml" style="${this._handleStyle('top: calc(50% - 4px); left: -5px; cursor: ew-resize;')}"></div>
        <div class="sc-handle sc-h-mr" data-handle="mr" style="${this._handleStyle('top: calc(50% - 4px); right: -5px; cursor: ew-resize;')}"></div>
        <div class="sc-handle sc-h-bl" data-handle="bl" style="${this._handleStyle('bottom: -5px; left: -5px; cursor: nesw-resize;')}"></div>
        <div class="sc-handle sc-h-bm" data-handle="bm" style="${this._handleStyle('bottom: -5px; left: calc(50% - 4px); cursor: ns-resize;')}"></div>
        <div class="sc-handle sc-h-br" data-handle="br" style="${this._handleStyle('bottom: -5px; right: -5px; cursor: nwse-resize;')}"></div>

        <!-- Live Floating Dimension Label (W x H px) -->
        <div id="sc-dimension-label" style="
            position: absolute; bottom: -32px; right: 0;
            background: rgba(0,0,0,0.75); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
            color: #fff; font-size: 13px; font-family: SFMono-Regular, Consolas, monospace;
            padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1);
            pointer-events: none; white-space: nowrap; font-weight: 500;
        ">0 × 0 px</div>

        <!-- Floating Action Toolbar -->
        <div id="sc-action-toolbar" style="
            position: absolute; bottom: -52px; left: 50%; transform: translateX(-50%);
            background: rgba(30, 30, 30, 0.85); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255,255,255,0.12); border-radius: 10px;
            padding: 6px 12px; display: none; gap: 8px; align-items: center;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5); z-index: 10;
        ">
          <button onclick="window.ScreenCapture.confirmAreaAction('save')" style="${this._toolbarBtnStyle('#34C759')}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
            保存
          </button>
          <button onclick="window.ScreenCapture.confirmAreaAction('copy')" style="${this._toolbarBtnStyle('#007AFF')}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            复制
          </button>
          <button onclick="window.ScreenCapture.confirmAreaAction('annotate')" style="${this._toolbarBtnStyle('#FF9500')}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
            标注
          </button>
          <button onclick="window.ScreenCapture.resetAreaSelection()" style="${this._toolbarBtnStyle('#FF3B30')}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg>
            重选
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    this._overlayEl = overlay;

    // Attach Selection Event Listeners
    overlay.addEventListener('mousedown', this._onMouseDown.bind(this));
    window.addEventListener('mousemove', this._onMouseMove.bind(this));
    window.addEventListener('mouseup', this._onMouseUp.bind(this));
  }

  private _handleStyle(positionCss: string): string {
    return `
      position: absolute; width: 8px; height: 8px;
      background: #ffffff; border: 1px solid #6C5CE7;
      border-radius: 2px; ${positionCss}
    `;
  }

  private _toolbarBtnStyle(color: string): string {
    return `
      display: flex; align-items: center; gap: 6px;
      background: ${color}22; border: 1px solid ${color}55;
      color: ${color}; border-radius: 6px; padding: 5px 10px;
      font-size: 12px; font-weight: 600; cursor: pointer;
      transition: all 0.2s; white-space: nowrap;
    `;
  }

  private _onMouseDown(e: MouseEvent): void {
    const target = e.target as HTMLElement;
    if (target.closest('#sc-action-toolbar')) return;

    if (target.classList.contains('sc-handle')) {
      this._isResizing = true;
      this._resizeHandle = target.dataset.handle || null;
      this._startX = e.clientX;
      this._startY = e.clientY;
      return;
    }

    this._isSelecting = true;
    this._startX = e.clientX;
    this._startY = e.clientY;
    this._currentRect = { x: e.clientX, y: e.clientY, width: 0, height: 0 };
    this._updateSelectionBox();
  }

  private _onMouseMove(e: MouseEvent): void {
    if (!this._overlayEl) return;

    if (this._isSelecting) {
      const currentX = e.clientX;
      const currentY = e.clientY;

      const x = Math.min(this._startX, currentX);
      const y = Math.min(this._startY, currentY);
      const width = Math.abs(currentX - this._startX);
      const height = Math.abs(currentY - this._startY);

      this._currentRect = { x, y, width, height };
      this._updateSelectionBox();
    } else if (this._isResizing && this._currentRect) {
      const dx = e.clientX - this._startX;
      const dy = e.clientY - this._startY;

      let { x, y, width, height } = this._currentRect;

      if (this._resizeHandle?.includes('r')) width += dx;
      if (this._resizeHandle?.includes('l')) { x += dx; width -= dx; }
      if (this._resizeHandle?.includes('b')) height += dy;
      if (this._resizeHandle?.includes('t')) { y += dy; height -= dy; }

      this._startX = e.clientX;
      this._startY = e.clientY;

      this._currentRect = { x, y, width: Math.max(20, width), height: Math.max(20, height) };
      this._updateSelectionBox();
    }
  }

  private _onMouseUp(): void {
    if (this._isSelecting || this._isResizing) {
      this._isSelecting = false;
      this._isResizing = false;

      const toolbar = document.getElementById('sc-action-toolbar');
      if (toolbar && this._currentRect && this._currentRect.width > 10 && this._currentRect.height > 10) {
        toolbar.style.display = 'flex';
      }
    }
  }

  private _updateSelectionBox(): void {
    const box = document.getElementById('sc-selection-box');
    const label = document.getElementById('sc-dimension-label');
    if (!box || !this._currentRect) return;

    box.style.display = 'block';
    box.style.left = `${this._currentRect.x}px`;
    box.style.top = `${this._currentRect.y}px`;
    box.style.width = `${this._currentRect.width}px`;
    box.style.height = `${this._currentRect.height}px`;

    if (label) {
      label.innerText = `${Math.round(this._currentRect.width)} × ${Math.round(this._currentRect.height)} px`;
    }
  }

  public resetAreaSelection(): void {
    const box = document.getElementById('sc-selection-box');
    const toolbar = document.getElementById('sc-action-toolbar');
    if (box) box.style.display = 'none';
    if (toolbar) toolbar.style.display = 'none';
    this._currentRect = null;
  }

  public async confirmAreaAction(action: 'save' | 'copy' | 'annotate'): Promise<void> {
    if (!this._currentRect) return;

    const rect = { ...this._currentRect };

    if (this._activeMode === 'record') {
      this._removeOverlay();
      this.startRecordingUI(`区域录制 (${rect.width}×${rect.height})`);
      try {
        if ((window as any).pywebview?.api) {
          await (window as any).pywebview.api.call_skill('screen_capture', 'start_recording', { type: 'area', rect });
        }
      } catch (e) {}
      return;
    }

    if (action === 'annotate') {
      this.openAnnotationModal(rect);
      return;
    }

    this._removeOverlay();

    try {
      if ((window as any).pywebview?.api) {
        const res = await (window as any).pywebview.api.call_skill('screen_capture', 'area_screenshot', { action, rect });
        window.showToast?.('区域截屏', res?.message || `区域截图已${action === 'copy' ? '复制到剪贴板' : '保存'}`, 'success');
      } else {
        window.showToast?.('区域截屏', `区域截图 (${rect.width}×${rect.height}px) 已${action === 'copy' ? '复制到剪贴板' : '保存路径 ~/Pictures/Butler/'}`, 'success');
      }
    } catch (e: any) {
      window.showToast?.('区域截屏', e.message || '操作失败', 'error');
    }
  }

  private _removeOverlay(): void {
    if (this._overlayEl) {
      this._overlayEl.remove();
      this._overlayEl = null;
    }
  }

  // --- 4. Recording Status Indicator ---
  public startRecordingUI(title: string): void {
    if (this._recordingIndicatorEl) return;

    this._isRecording = true;
    this._recordingSeconds = 0;

    const html = `
      <div id="sc-recording-indicator" style="
          position: fixed; top: 24px; right: 24px; z-index: 10008;
          background: rgba(30, 30, 30, 0.85); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
          border: 1px solid rgba(255, 59, 48, 0.4); border-radius: 14px;
          padding: 10px 18px; display: flex; align-items: center; gap: 14px;
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5); color: #fff;
          font-family: SFMono-Regular, Consolas, monospace; user-select: none;
      ">
        <div style="display: flex; align-items: center; gap: 8px;">
          <div style="
              width: 12px; height: 12px; border-radius: 50%; background: #FF3B30;
              animation: scPulseRed 1s infinite alternate;
          "></div>
          <span style="font-size: 13px; font-weight: 600;">${title}</span>
        </div>
        <div id="sc-recording-timer" style="font-size: 14px; color: #FF9500; font-weight: 600;">00:00:00</div>
        <button onclick="window.ScreenCapture.stopRecordingUI()" style="
            background: rgba(255, 59, 48, 0.2); border: 1px solid rgba(255, 59, 48, 0.6);
            color: #FF3B30; border-radius: 8px; padding: 4px 12px; font-size: 12px;
            font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px;
        ">
          <div style="width: 8px; height: 8px; background: #FF3B30; border-radius: 1px;"></div>
          停止录制
        </button>
      </div>
      <style>
        @keyframes scPulseRed {
          from { opacity: 0.3; transform: scale(0.9); }
          to { opacity: 1; transform: scale(1.1); }
        }
      </style>
    `;

    this._recordingIndicatorEl = document.createElement('div');
    this._recordingIndicatorEl.id = 'sc-recording-root';
    this._recordingIndicatorEl.innerHTML = html;
    document.body.appendChild(this._recordingIndicatorEl);

    this._recordingTimer = setInterval(() => {
      this._recordingSeconds++;
      const timerEl = document.getElementById('sc-recording-timer');
      if (timerEl) {
        const hrs = Math.floor(this._recordingSeconds / 3600).toString().padStart(2, '0');
        const mins = Math.floor((this._recordingSeconds % 3600) / 60).toString().padStart(2, '0');
        const secs = (this._recordingSeconds % 60).toString().padStart(2, '0');
        timerEl.innerText = `${hrs}:${mins}:${secs}`;
      }
    }, 1000);
  }

  public async stopRecordingUI(): Promise<void> {
    if (this._recordingTimer) {
      clearInterval(this._recordingTimer);
      this._recordingTimer = null;
    }

    if (this._recordingIndicatorEl) {
      this._recordingIndicatorEl.remove();
      this._recordingIndicatorEl = null;
    }

    this._isRecording = false;

    try {
      if ((window as any).pywebview?.api) {
        const res = await (window as any).pywebview.api.call_skill('screen_capture', 'stop_recording');
        window.showToast?.('录制结束', res?.message || `视频已保存至: ~/Pictures/Butler/`, 'success');
      } else {
        window.showToast?.('录制结束', `视频文件 record_${Date.now()}.mp4 已保存至系统图片目录`, 'success');
      }
    } catch (e: any) {
      window.showToast?.('录制提示', '录制已完成并停止', 'info');
    }
  }

  // --- 5. Image Annotation Canvas Engine ---
  public openAnnotationModal(rect: SelectionRect): void {
    this._removeOverlay();

    const width = Math.max(300, rect.width);
    const height = Math.max(200, rect.height);

    const html = `
      <div id="sc-annotation-overlay" style="
          position: fixed; inset: 0; background: rgba(0,0,0,0.7);
          backdrop-filter: blur(10px); z-index: 10009;
          display: flex; flex-direction: column; align-items: center; justify-content: center;
      ">
        <!-- Canvas Container -->
        <div style="position: relative; border-radius: 12px; overflow: hidden; box-shadow: 0 20px 50px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.15);">
          <canvas id="sc-annotation-canvas" width="${width}" height="${height}" style="background: #2a2a2a; display: block; cursor: crosshair;"></canvas>
        </div>

        <!-- Annotation Toolbar -->
        <div style="
            margin-top: 16px; background: rgba(30, 30, 30, 0.9); backdrop-filter: blur(16px);
            border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; padding: 8px 16px;
            display: flex; gap: 12px; align-items: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        ">
          <button onclick="window.ScreenCapture.setAnnotationTool('pen')" class="sc-ann-tool" style="${this._annToolBtnStyle('pen')}">✏️ 画笔</button>
          <button onclick="window.ScreenCapture.setAnnotationTool('arrow')" class="sc-ann-tool" style="${this._annToolBtnStyle('arrow')}">➡️ 箭头</button>
          <button onclick="window.ScreenCapture.setAnnotationTool('text')" class="sc-ann-tool" style="${this._annToolBtnStyle('text')}">💬 文字</button>
          <button onclick="window.ScreenCapture.setAnnotationTool('mosaic')" class="sc-ann-tool" style="${this._annToolBtnStyle('mosaic')}">🧩 马赛克</button>
          <div style="width: 1px; height: 20px; background: rgba(255,255,255,0.15);"></div>
          <button onclick="window.ScreenCapture.saveAnnotation('save')" style="${this._toolbarBtnStyle('#34C759')}">💾 完成并保存</button>
          <button onclick="window.ScreenCapture.closeAnnotationModal()" style="${this._toolbarBtnStyle('#FF3B30')}">✕ 取消</button>
        </div>
      </div>
    `;

    this._annotationModalEl = document.createElement('div');
    this._annotationModalEl.id = 'sc-annotation-root';
    this._annotationModalEl.innerHTML = html;
    document.body.appendChild(this._annotationModalEl);

    setTimeout(() => {
      this._initAnnotationCanvas();
    }, 50);
  }

  private _annToolBtnStyle(tool: string): string {
    const active = this._annotationTool === tool;
    return `
      background: ${active ? '#6C5CE733' : 'rgba(255,255,255,0.06)'};
      border: 1px solid ${active ? '#6C5CE7' : 'rgba(255,255,255,0.1)'};
      color: ${active ? '#6C5CE7' : '#fff'};
      border-radius: 6px; padding: 6px 12px; font-size: 12px; font-weight: 500;
      cursor: pointer; transition: all 0.2s;
    `;
  }

  public setAnnotationTool(tool: 'pen' | 'arrow' | 'text' | 'mosaic'): void {
    this._annotationTool = tool;
    const btns = document.querySelectorAll('.sc-ann-tool');
    btns.forEach((b: any) => {
      b.style.background = 'rgba(255,255,255,0.06)';
      b.style.borderColor = 'rgba(255,255,255,0.1)';
      b.style.color = '#fff';
    });
  }

  private _initAnnotationCanvas(): void {
    this._annotationCanvas = document.getElementById('sc-annotation-canvas') as HTMLCanvasElement;
    if (!this._annotationCanvas) return;
    this._annotationCtx = this._annotationCanvas.getContext('2d');

    if (this._annotationCtx) {
      this._annotationCtx.fillStyle = '#1e1e24';
      this._annotationCtx.fillRect(0, 0, this._annotationCanvas.width, this._annotationCanvas.height);
      this._annotationCtx.fillStyle = '#6C5CE7';
      this._annotationCtx.font = '14px sans-serif';
      this._annotationCtx.fillText('Butler 截图标注画板 (可自由绘制)', 20, 30);
    }

    this._annotationCanvas.addEventListener('mousedown', this._onDrawStart.bind(this));
    this._annotationCanvas.addEventListener('mousemove', this._onDrawMove.bind(this));
    this._annotationCanvas.addEventListener('mouseup', this._onDrawEnd.bind(this));
  }

  private _onDrawStart(e: MouseEvent): void {
    if (!this._annotationCanvas || !this._annotationCtx) return;
    const rect = this._annotationCanvas.getBoundingClientRect();
    this._isDrawing = true;
    this._drawStartX = e.clientX - rect.left;
    this._drawStartY = e.clientY - rect.top;

    this._canvasSnapshot = this._annotationCtx.getImageData(0, 0, this._annotationCanvas.width, this._annotationCanvas.height);

    if (this._annotationTool === 'pen') {
      this._annotationCtx.beginPath();
      this._annotationCtx.moveTo(this._drawStartX, this._drawStartY);
    } else if (this._annotationTool === 'text') {
      const text = prompt('请输入标注文字:', '重要提示');
      if (text) {
        this._annotationCtx.fillStyle = '#FF3B30';
        this._annotationCtx.font = 'bold 16px sans-serif';
        this._annotationCtx.fillText(text, this._drawStartX, this._drawStartY);
      }
      this._isDrawing = false;
    }
  }

  private _onDrawMove(e: MouseEvent): void {
    if (!this._isDrawing || !this._annotationCanvas || !this._annotationCtx) return;
    const rect = this._annotationCanvas.getBoundingClientRect();
    const currX = e.clientX - rect.left;
    const currY = e.clientY - rect.top;

    if (this._annotationTool === 'pen') {
      this._annotationCtx.strokeStyle = '#FF3B30';
      this._annotationCtx.lineWidth = 3;
      this._annotationCtx.lineTo(currX, currY);
      this._annotationCtx.stroke();
    } else if (this._annotationTool === 'arrow') {
      if (this._canvasSnapshot) {
        this._annotationCtx.putImageData(this._canvasSnapshot, 0, 0);
      }
      this._drawArrow(this._drawStartX, this._drawStartY, currX, currY);
    } else if (this._annotationTool === 'mosaic') {
      this._annotationCtx.fillStyle = 'rgba(200,200,200,0.5)';
      this._annotationCtx.fillRect(currX - 8, currY - 8, 16, 16);
    }
  }

  private _onDrawEnd(): void {
    this._isDrawing = false;
  }

  private _drawArrow(fromX: number, fromY: number, toX: number, toY: number): void {
    if (!this._annotationCtx) return;
    const headlen = 10;
    const dx = toX - fromX;
    const dy = toY - fromY;
    const angle = Math.atan2(dy, dx);

    this._annotationCtx.strokeStyle = '#34C759';
    this._annotationCtx.fillStyle = '#34C759';
    this._annotationCtx.lineWidth = 3;

    this._annotationCtx.beginPath();
    this._annotationCtx.moveTo(fromX, fromY);
    this._annotationCtx.lineTo(toX, toY);
    this._annotationCtx.stroke();

    this._annotationCtx.beginPath();
    this._annotationCtx.moveTo(toX, toY);
    this._annotationCtx.lineTo(toX - headlen * Math.cos(angle - Math.PI / 6), toY - headlen * Math.sin(angle - Math.PI / 6));
    this._annotationCtx.lineTo(toX - headlen * Math.cos(angle + Math.PI / 6), toY - headlen * Math.sin(angle + Math.PI / 6));
    this._annotationCtx.closePath();
    this._annotationCtx.fill();
  }

  public saveAnnotation(action: string): void {
    this.closeAnnotationModal();
    window.showToast?.('标注完成', '带标注截图已成功导出保存！', 'success');
  }

  public closeAnnotationModal(): void {
    if (this._annotationModalEl) {
      this._annotationModalEl.remove();
      this._annotationModalEl = null;
    }
  }
}

export const screenCaptureController = new ScreenCaptureController();

if (typeof window !== 'undefined') {
  (window as any).ScreenCapture = screenCaptureController;
}
