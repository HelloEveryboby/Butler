/**
 * Butler Video Player — 本地原生视频播放器前端控制面板
 *
 * 界面风格：Glassmorphism 玻璃拟态 + Apple 设计语言
 * 通过 WebSocket 与后端 mpv/VLC 通信，控制本地播放器。
 *
 * 快捷键：
 *   Space: 暂停/播放 | ←/→: 快退/快进 5s | ↑/↓: 音量
 *   F: 全屏 | M: 静音 | S: 截图 | C: 字幕 | N/P: 上下集
 */

interface VideoInfo {
  video_id: string;
  title: string;
  path: string;
  container: string;
  video_codec: string;
  audio_codec: string;
  resolution: string;
  duration: number;
  resume_from?: number;
}

interface PlayerStatus {
  state: 'idle' | 'playing' | 'paused' | 'seeking' | 'buffering' | 'ended' | 'error';
  position: number;
  duration: number;
  speed: number;
  volume: number;
  muted: boolean;
  subtitle_visible: boolean;
  audio_tracks: AudioTrackInfo[];
  subtitle_tracks: SubtitleTrackInfo[];
  video: VideoInfo | null;
  playlist: { current_index: number; total: number };
}

interface AudioTrackInfo {
  index: number;
  language: string;
  title: string;
  channels: number;
}

interface SubtitleTrackInfo {
  index: number;
  language: string;
  title: string;
  codec: string;
  is_external: boolean;
}

type WSBroadcaster = (msg: object) => void;

class ButlerVideoPlayer {
  private container: HTMLElement;
  private apiBase: string;
  private ws: WebSocket | null = null;
  private status: PlayerStatus | null = null;
  private updateTimer: number | null = null;

  // UI 元素
  private panel: HTMLElement | null = null;
  private titleEl: HTMLElement | null = null;
  private stateIconEl: HTMLElement | null = null;
  private positionEl: HTMLElement | null = null;
  private durationEl: HTMLElement | null = null;
  private progressEl: HTMLElement | null = null;
  private progressFillEl: HTMLElement | null = null;
  private progressHandleEl: HTMLElement | null = null;
  private volumeEl: HTMLElement | null = null;
  private volumeFillEl: HTMLElement | null = null;
  private speedEl: HTMLElement | null = null;
  private codecInfoEl: HTMLElement | null = null;
  private audioSelectEl: HTMLSelectElement | null = null;
  private subtitleSelectEl: HTMLSelectElement | null = null;

  private isDraggingProgress = false;

  constructor(container: HTMLElement, apiBase: string = '') {
    this.container = container;
    this.apiBase = apiBase || window.location.origin;
    this.injectStyles();
    this.createPanel();
    this.bindKeyboard();
    this.connectWebSocket();
    this.startStatusPolling();
  }

  // ══════════════════════════════════════════
  // WebSocket 连接
  // ══════════════════════════════════════════

  private connectWebSocket(): void {
    const wsUrl = this.apiBase.replace(/^http/, 'ws') + '/ws/video';
    try {
      this.ws = new WebSocket(wsUrl);
      this.ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          this.handleWSMessage(msg);
        } catch {}
      };
      this.ws.onclose = () => {
        setTimeout(() => this.connectWebSocket(), 3000);
      };
    } catch {}
  }

  private sendWS(msg: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private handleWSMessage(msg: any): void {
    switch (msg.type) {
      case 'state_change':
        this.onStateChange(msg.state);
        break;
      case 'position_update':
        this.onPositionUpdate(msg.position, msg.duration, msg.speed);
        break;
      case 'media_loaded':
        this.onMediaLoaded(msg);
        break;
      case 'error':
        this.showError(msg.message);
        break;
    }
  }

  // ══════════════════════════════════════════
  // UI 构建（Glassmorphism 风格）
  // ══════════════════════════════════════════

  private createPanel(): void {
    this.panel = document.createElement('div');
    this.panel.className = 'bvp-panel glass-surface';
    this.panel.innerHTML = `
      <!-- 顶部信息栏 -->
      <div class="bvp-header">
        <button class="bvp-btn bvp-back" title="返回媒体库">
          <i class="fas fa-chevron-left"></i>
        </button>
        <div class="bvp-title-area">
          <span class="bvp-title">未在播放</span>
          <span class="bvp-codec-info"></span>
        </div>
        <div class="bvp-header-actions">
          <button class="bvp-btn bvp-fav" title="收藏"><i class="far fa-heart"></i></button>
          <button class="bvp-btn bvp-playlist" title="播放列表"><i class="fas fa-list"></i></button>
        </div>
      </div>

      <!-- 状态指示区 -->
      <div class="bvp-status-area">
        <div class="bvp-state-icon"><i class="fas fa-film"></i></div>
        <div class="bvp-state-text">选择视频开始播放</div>
      </div>

      <!-- 进度条 -->
      <div class="bvp-progress-container">
        <span class="bvp-time bvp-position">00:00</span>
        <div class="bvp-progress-bar">
          <div class="bvp-progress-bg"></div>
          <div class="bvp-progress-fill"></div>
          <div class="bvp-progress-handle"></div>
        </div>
        <span class="bvp-time bvp-duration">00:00</span>
      </div>

      <!-- 控制按钮行 -->
      <div class="bvp-controls">
        <div class="bvp-controls-left">
          <button class="bvp-btn bvp-prev" title="上一集"><i class="fas fa-backward-step"></i></button>
          <button class="bvp-btn bvp-play" title="播放/暂停"><i class="fas fa-play"></i></button>
          <button class="bvp-btn bvp-next" title="下一集"><i class="fas fa-forward-step"></i></button>
          <button class="bvp-btn bvp-stop" title="停止"><i class="fas fa-stop"></i></button>
        </div>
        <div class="bvp-controls-center">
          <button class="bvp-btn bvp-rw" title="快退 10s"><i class="fas fa-backward"></i></button>
          <button class="bvp-btn bvp-ff" title="快进 10s"><i class="fas fa-forward"></i></button>
        </div>
        <div class="bvp-controls-right">
          <div class="bvp-volume-group">
            <button class="bvp-btn bvp-mute" title="静音"><i class="fas fa-volume-high"></i></button>
            <div class="bvp-volume-bar">
              <div class="bvp-volume-fill"></div>
            </div>
          </div>
          <div class="bvp-speed-group">
            <button class="bvp-btn bvp-speed" title="播放速度">1.0x</button>
          </div>
        </div>
      </div>

      <!-- 音轨/字幕选择行 -->
      <div class="bvp-tracks">
        <div class="bvp-track-group">
          <label><i class="fas fa-headphones"></i> 音轨</label>
          <select class="bvp-audio-select"><option value="">-</option></select>
        </div>
        <div class="bvp-track-group">
          <label><i class="fas fa-closed-captioning"></i> 字幕</label>
          <select class="bvp-subtitle-select"><option value="">-</option></select>
          <button class="bvp-btn bvp-sub-toggle" title="字幕开关"><i class="fas fa-eye"></i></button>
        </div>
        <div class="bvp-track-group bvp-track-actions">
          <button class="bvp-btn bvp-screenshot" title="截图"><i class="fas fa-camera"></i></button>
        </div>
      </div>
    `;

    this.container.appendChild(this.panel);

    // 缓存 DOM 引用
    this.titleEl = this.panel.querySelector('.bvp-title')!;
    this.stateIconEl = this.panel.querySelector('.bvp-state-icon')!;
    this.positionEl = this.panel.querySelector('.bvp-position')!;
    this.durationEl = this.panel.querySelector('.bvp-duration')!;
    this.progressEl = this.panel.querySelector('.bvp-progress-bar')!;
    this.progressFillEl = this.panel.querySelector('.bvp-progress-fill')!;
    this.progressHandleEl = this.panel.querySelector('.bvp-progress-handle')!;
    this.volumeEl = this.panel.querySelector('.bvp-volume-bar')!;
    this.volumeFillEl = this.panel.querySelector('.bvp-volume-fill')!;
    this.speedEl = this.panel.querySelector('.bvp-speed')!;
    this.codecInfoEl = this.panel.querySelector('.bvp-codec-info')!;
    this.audioSelectEl = this.panel.querySelector('.bvp-audio-select') as HTMLSelectElement;
    this.subtitleSelectEl = this.panel.querySelector('.bvp-subtitle-select') as HTMLSelectElement;

    this.bindUIEvents();
  }

  private bindUIEvents(): void {
    if (!this.panel) return;

    // 播放控制按钮
    this.panel.querySelector('.bvp-play')?.addEventListener('click', () => this.cmd('toggle'));
    this.panel.querySelector('.bvp-stop')?.addEventListener('click', () => this.cmd('stop'));
    this.panel.querySelector('.bvp-prev')?.addEventListener('click', () => this.cmd('prev'));
    this.panel.querySelector('.bvp-next')?.addEventListener('click', () => this.cmd('next'));
    this.panel.querySelector('.bvp-rw')?.addEventListener('click', () => this.cmd('seek_relative', { offset: -10 }));
    this.panel.querySelector('.bvp-ff')?.addEventListener('click', () => this.cmd('seek_relative', { offset: 10 }));

    // 静音
    this.panel.querySelector('.bvp-mute')?.addEventListener('click', () => {
      this.cmd('mute', { muted: !this.status?.muted });
    });

    // 倍速循环
    const speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0];
    this.speedEl?.addEventListener('click', () => {
      const current = this.status?.speed || 1.0;
      const idx = speeds.indexOf(current);
      const next = speeds[(idx + 1) % speeds.length];
      this.cmd('speed', { value: next });
    });

    // 进度条拖拽
    this.progressEl?.addEventListener('mousedown', (e) => this.onProgressMouseDown(e));
    document.addEventListener('mousemove', (e) => this.onProgressMouseMove(e));
    document.addEventListener('mouseup', () => this.onProgressMouseUp());

    // 音量条
    this.volumeEl?.addEventListener('click', (e) => {
      const rect = this.volumeEl!.getBoundingClientRect();
      const pct = (e.clientX - rect.left) / rect.width * 100;
      this.cmd('volume', { value: Math.max(0, Math.min(100, pct)) });
    });

    // 音轨选择
    this.audioSelectEl?.addEventListener('change', () => {
      const idx = parseInt(this.audioSelectEl!.value);
      if (!isNaN(idx)) this.cmd('audio_track', { index: idx });
    });

    // 字幕选择
    this.subtitleSelectEl?.addEventListener('change', () => {
      const idx = parseInt(this.subtitleSelectEl!.value);
      if (!isNaN(idx)) this.cmd('subtitle_track', { index: idx });
    });

    // 字幕开关
    this.panel.querySelector('.bvp-sub-toggle')?.addEventListener('click', () => {
      this.cmd('subtitle_toggle');
    });

    // 截图
    this.panel.querySelector('.bvp-screenshot')?.addEventListener('click', () => {
      this.cmd('screenshot');
    });
  }

  // ══════════════════════════════════════════
  // 进度条拖拽
  // ══════════════════════════════════════════

  private onProgressMouseDown(e: MouseEvent): void {
    this.isDraggingProgress = true;
    this.updateProgressFromMouse(e);
  }

  private onProgressMouseMove(e: MouseEvent): void {
    if (this.isDraggingProgress) {
      this.updateProgressFromMouse(e);
    }
  }

  private onProgressMouseUp(): void {
    if (this.isDraggingProgress) {
      this.isDraggingProgress = false;
      const duration = this.status?.duration || 0;
      if (duration > 0 && this.progressFillEl) {
        const fillWidth = parseFloat(this.progressFillEl.style.width) || 0;
        this.cmd('seek', { position: fillWidth / 100 * duration });
      }
    }
  }

  private updateProgressFromMouse(e: MouseEvent): void {
    if (!this.progressEl || !this.status) return;
    const rect = this.progressEl.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const pos = pct * (this.status.duration || 0);
    this.positionEl!.textContent = this.formatTime(pos);
    this.progressFillEl!.style.width = `${pct * 100}%`;
    this.progressHandleEl!.style.left = `${pct * 100}%`;
  }

  // ══════════════════════════════════════════
  // 快捷键
  // ══════════════════════════════════════════

  private bindKeyboard(): void {
    document.addEventListener('keydown', (e) => {
      // 忽略输入框内的按键
      if ((e.target as HTMLElement).tagName === 'INPUT' ||
          (e.target as HTMLElement).tagName === 'TEXTAREA') return;

      switch (e.key) {
        case ' ':
          e.preventDefault();
          this.cmd('toggle');
          break;
        case 'ArrowLeft':
          e.preventDefault();
          this.cmd('seek_relative', { offset: e.shiftKey ? -30 : -5 });
          break;
        case 'ArrowRight':
          e.preventDefault();
          this.cmd('seek_relative', { offset: e.shiftKey ? 30 : 5 });
          break;
        case 'ArrowUp':
          e.preventDefault();
          this.cmd('volume', { value: Math.min(100, (this.status?.volume || 80) + 5) });
          break;
        case 'ArrowDown':
          e.preventDefault();
          this.cmd('volume', { value: Math.max(0, (this.status?.volume || 80) - 5) });
          break;
        case 'm': case 'M':
          this.cmd('mute', { muted: !this.status?.muted });
          break;
        case 's': case 'S':
          if (!e.ctrlKey) this.cmd('screenshot');
          break;
        case 'c': case 'C':
          this.cmd('subtitle_toggle');
          break;
        case 'n': case 'N':
          this.cmd('next');
          break;
        case 'p': case 'P':
          this.cmd('prev');
          break;
        case '[':
          this.cmd('speed', { value: Math.max(0.25, (this.status?.speed || 1) - 0.25) });
          break;
        case ']':
          this.cmd('speed', { value: Math.min(4, (this.status?.speed || 1) + 0.25) });
          break;
        case '\\':
          this.cmd('speed', { value: 1.0 });
          break;
      }
    });
  }

  // ══════════════════════════════════════════
  // API 调用
  // ══════════════════════════════════════════

  private async cmd(action: string, params: object = {}): Promise<void> {
    // 优先 WebSocket
    this.sendWS({ type: 'command', action, ...params });

    // 同时 REST API 备选
    try {
      const endpoint = this.actionToEndpoint(action);
      if (endpoint) {
        await fetch(`${this.apiBase}${endpoint.url}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params),
        });
      }
    } catch {}
  }

  private actionToEndpoint(action: string): { url: string } | null {
    const map: Record<string, string> = {
      'toggle': '/api/video/toggle',
      'stop': '/api/video/stop',
      'seek': '/api/video/seek',
      'seek_relative': '/api/video/seek/relative',
      'speed': '/api/video/speed',
      'volume': '/api/video/volume',
      'mute': '/api/video/mute',
      'audio_track': '/api/video/audio/track',
      'subtitle_track': '/api/video/subtitle/track',
      'subtitle_toggle': '/api/video/subtitle/toggle',
      'next': '/api/video/next',
      'prev': '/api/video/prev',
      'screenshot': '/api/video/screenshot',
    };
    const url = map[action];
    return url ? { url } : null;
  }

  // ══════════════════════════════════════════
  // 状态轮询
  // ══════════════════════════════════════════

  private startStatusPolling(): void {
    this.updateTimer = window.setInterval(() => this.fetchStatus(), 2000);
  }

  private async fetchStatus(): Promise<void> {
    try {
      const res = await fetch(`${this.apiBase}/api/video/status`);
      const json = await res.json();
      if (json.success && json.data) {
        this.updateUI(json.data as PlayerStatus);
      }
    } catch {}
  }

  // ══════════════════════════════════════════
  // 事件处理
  // ══════════════════════════════════════════

  private onStateChange(state: string): void {
    if (!this.panel) return;
    const icon = this.stateIconEl?.querySelector('i');
    if (!icon) return;

    this.panel.setAttribute('data-state', state);
    switch (state) {
      case 'playing':
        icon.className = 'fas fa-volume-high';
        this.panel.querySelector('.bvp-play i')!.className = 'fas fa-pause';
        break;
      case 'paused':
        icon.className = 'fas fa-pause';
        this.panel.querySelector('.bvp-play i')!.className = 'fas fa-play';
        break;
      case 'buffering':
        icon.className = 'fas fa-spinner fa-spin';
        break;
      case 'ended':
        icon.className = 'fas fa-check-circle';
        this.panel.querySelector('.bvp-play i')!.className = 'fas fa-play';
        break;
      case 'error':
        icon.className = 'fas fa-exclamation-triangle';
        break;
      default:
        icon.className = 'fas fa-film';
        this.panel.querySelector('.bvp-play i')!.className = 'fas fa-play';
    }
  }

  private onPositionUpdate(position: number, duration: number, speed: number): void {
    if (this.isDraggingProgress) return;
    if (this.positionEl) this.positionEl.textContent = this.formatTime(position);
    if (this.durationEl) this.durationEl.textContent = this.formatTime(duration);
    if (this.progressFillEl && duration > 0) {
      const pct = position / duration * 100;
      this.progressFillEl.style.width = `${pct}%`;
      if (this.progressHandleEl) this.progressHandleEl.style.left = `${pct}%`;
    }
    if (this.speedEl) this.speedEl.textContent = `${speed.toFixed(1)}x`;
  }

  private onMediaLoaded(data: any): void {
    if (this.titleEl) this.titleEl.textContent = data.title || '未知';
    if (this.codecInfoEl) {
      const parts = [];
      if (data.container) parts.push(data.container.toUpperCase());
      if (data.video_codec) parts.push(data.video_codec.toUpperCase());
      if (data.audio_codec) parts.push(data.audio_codec.toUpperCase());
      if (data.resolution) parts.push(data.resolution);
      this.codecInfoEl.textContent = parts.join(' · ');
    }
  }

  // ══════════════════════════════════════════
  // UI 更新
  // ══════════════════════════════════════════

  private updateUI(status: PlayerStatus): void {
    this.status = status;
    this.onStateChange(status.state);
    this.onPositionUpdate(status.position, status.duration, status.speed);

    // 音量
    if (this.volumeFillEl) {
      this.volumeFillEl.style.width = `${status.volume}%`;
    }
    const muteIcon = this.panel?.querySelector('.bvp-mute i');
    if (muteIcon) {
      muteIcon.className = status.muted ? 'fas fa-volume-xmark' : 'fas fa-volume-high';
    }

    // 音轨选择
    if (this.audioSelectEl && status.audio_tracks) {
      const current = this.audioSelectEl.value;
      this.audioSelectEl.innerHTML = status.audio_tracks.map(t =>
        `<option value="${t.index}" ${t.index === parseInt(current) ? 'selected' : ''}>` +
        `${t.language || '未知'} ${t.channels > 2 ? `${t.channels}ch` : ''} ${t.title ? `(${t.title})` : ''}` +
        `</option>`
      ).join('');
    }

    // 字幕选择
    if (this.subtitleSelectEl && status.subtitle_tracks) {
      const current = this.subtitleSelectEl.value;
      this.subtitleSelectEl.innerHTML =
        `<option value="-1">关闭</option>` +
        status.subtitle_tracks.map(t =>
          `<option value="${t.index}" ${t.index === parseInt(current) ? 'selected' : ''}>` +
          `${t.language || '未知'} ${t.is_external ? '(外挂)' : ''} ${t.title ? `(${t.title})` : ''}` +
          `</option>`
        ).join('');
    }

    // 视频标题
    if (status.video && this.titleEl) {
      this.titleEl.textContent = status.video.title || '未知';
    }
  }

  private showError(msg: string): void {
    console.error('[ButlerVideoPlayer]', msg);
  }

  // ══════════════════════════════════════════
  // 公开方法
  // ══════════════════════════════════════════

  /** 播放指定视频 */
  async playVideo(videoId: string, resume: boolean = true): Promise<void> {
    try {
      const url = `${this.apiBase}/api/video/play/${videoId}?resume=${resume}`;
      const res = await fetch(url, { method: 'POST' });
      const json = await res.json();
      if (json.success) {
        this.onMediaLoaded(json.data);
      }
    } catch (e) {
      console.error('播放失败:', e);
    }
  }

  /** 显示/隐藏面板 */
  toggle(): void {
    if (this.panel) {
      this.panel.classList.toggle('bvp-hidden');
    }
  }

  show(): void {
    this.panel?.classList.remove('bvp-hidden');
  }

  hide(): void {
    this.panel?.classList.add('bvp-hidden');
  }

  /** 销毁 */
  destroy(): void {
    if (this.updateTimer) clearInterval(this.updateTimer);
    this.ws?.close();
    this.panel?.remove();
  }

  // ══════════════════════════════════════════
  // 工具函数
  // ══════════════════════════════════════════

  private formatTime(seconds: number): string {
    if (!seconds || seconds < 0) return '00:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  // ══════════════════════════════════════════
  // 样式注入
  // ══════════════════════════════════════════

  private injectStyles(): void {
    if (document.getElementById('bvp-styles')) return;
    const link = document.createElement('link');
    link.id = 'bvp-styles';
    link.rel = 'stylesheet';
    link.href = 'src/css/video_player.css';
    document.head.appendChild(link);
  }
}
