/**
 * Butler Download Manager — 下载管理器前端
 * 集成到 Butler 玻璃拟态界面
 */

// ============================================================
// 类型定义
// ============================================================

interface DownloadTask {
  gid: string;
  status: string;          // active / waiting / paused / complete / error
  filename: string;
  total_length: number;
  completed_length: number;
  total_human: string;
  completed_human: string;
  progress: number;        // 0-100
  download_speed: number;
  speed_human: string;
  remaining_seconds: number;
  remaining_human: string;
  connections: number;
  dir: string;
  error_code?: string;
  error_message?: string;
}

interface DownloadSpeed {
  download_speed: number;
  upload_speed: number;
  num_active: number;
  num_waiting: number;
  num_stopped: number;
}

interface DownloadState {
  active: DownloadTask[];
  waiting: DownloadTask[];
  stopped: DownloadTask[];
}

// ============================================================
// RPC 通信
// ============================================================

class DownloadRPC {
  private port: number;
  private secret: string;

  constructor(port = 6800, secret = 'butler_download') {
    this.port = port;
    this.secret = secret;
  }

  private async call(method: string, params: any[] = []): Promise<any> {
    const resp = await fetch(`http://127.0.0.1:${this.port}/jsonrpc`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: `butler-${Date.now()}`,
        method,
        params: [`token:${this.secret}`, ...params],
      }),
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error.message);
    return data.result;
  }

  async addUri(url: string, options?: any): Promise<string> {
    return this.call('aria2.addUri', [[url], options || {}]);
  }

  async addMagnet(magnet: string, options?: any): Promise<string> {
    return this.call('aria2.addUri', [[magnet], options || {}]);
  }

  async pause(gid: string): Promise<void> { await this.call('aria2.pause', [gid]); }
  async resume(gid: string): Promise<void> { await this.call('aria2.resume', [gid]); }
  async remove(gid: string): Promise<void> { await this.call('aria2.forceRemove', [gid]); }
  async pauseAll(): Promise<void> { await this.call('aria2.pauseAll'); }
  async resumeAll(): Promise<void> { await this.call('aria2.resumeAll'); }

  async getActive(): Promise<any[]> { return (await this.call('aria2.tellActive')) || []; }
  async getWaiting(): Promise<any[]> { return (await this.call('aria2.tellWaiting', [0, 100])) || []; }
  async getStopped(): Promise<any[]> { return (await this.call('aria2.tellStopped', [0, 100])) || []; }
  async getGlobalStat(): Promise<any> { return this.call('aria2.getGlobalStat'); }
}

// ============================================================
// 格式化工具
// ============================================================

function humanSize(bytes: number): string {
  if (bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
  return `${bytes.toFixed(1)} ${units[i]}`;
}

function humanTime(seconds: number): string {
  if (seconds <= 0) return '未知';
  if (seconds < 60) return `${Math.floor(seconds)}秒`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${Math.floor(seconds % 60)}秒`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}小时${m}分`;
}

function formatTask(raw: any): DownloadTask {
  const total = parseInt(raw.totalLength || '0');
  const completed = parseInt(raw.completedLength || '0');
  const speed = parseInt(raw.downloadSpeed || '0');
  const progress = total > 0 ? (completed / total) * 100 : 0;
  const files = raw.files || [];
  const filename = files[0]?.path ? files[0].path.split('/').pop().split('\\').pop() : raw.gid;
  const remaining = speed > 0 ? (total - completed) / speed : 0;

  return {
    gid: raw.gid,
    status: raw.status,
    filename,
    total_length: total,
    completed_length: completed,
    total_human: humanSize(total),
    completed_human: humanSize(completed),
    progress: Math.round(progress * 10) / 10,
    download_speed: speed,
    speed_human: `${humanSize(speed)}/s`,
    remaining_seconds: Math.round(remaining),
    remaining_human: humanTime(remaining),
    connections: parseInt(raw.connections || '0'),
    dir: raw.dir || '',
    error_code: raw.errorCode,
    error_message: raw.errorMessage,
  };
}

// ============================================================
// 下载管理器 UI
// ============================================================

class DownloadManagerUI {
  private rpc: DownloadRPC;
  private container: HTMLElement | null = null;
  private isVisible = false;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private currentTasks: DownloadState = { active: [], waiting: [], stopped: [] };

  constructor() {
    this.rpc = new DownloadRPC();
  }

  // ---------- 初始化 ----------
  init(): void {
    this.injectStyles();
    this.createContainer();
    this.startPolling();
    console.log('[ButlerDownload] Download manager initialized');
  }

  // ---------- 显示/隐藏 ----------
  toggle(): void {
    if (this.isVisible) {
      this.hide();
    } else {
      this.show();
    }
  }

  show(): void {
    if (!this.container) this.createContainer();
    this.container!.style.display = 'flex';
    this.isVisible = true;
    this.refresh();
  }

  hide(): void {
    if (this.container) this.container.style.display = 'none';
    this.isVisible = false;
  }

  // ---------- 创建容器 ----------
  private createContainer(): void {
    this.container = document.createElement('div');
    this.container.id = 'butler-download-manager';
    this.container.innerHTML = `
      <div class="dm-header">
        <div class="dm-title">
          <span class="dm-icon">📥</span>
          <span>下载管理器</span>
        </div>
        <div class="dm-header-actions">
          <button class="dm-btn dm-btn-sm" id="dm-add" title="新建下载">+</button>
          <button class="dm-btn dm-btn-sm" id="dm-pause-all" title="全部暂停">⏸</button>
          <button class="dm-btn dm-btn-sm" id="dm-resume-all" title="全部恢复">▶</button>
          <button class="dm-btn dm-btn-sm dm-btn-close" id="dm-close" title="关闭">✕</button>
        </div>
      </div>

      <div class="dm-speed-bar">
        <span class="dm-speed-down">↓ <span id="dm-speed-down">0 B/s</span></span>
        <span class="dm-speed-up">↑ <span id="dm-speed-up">0 B/s</span></span>
        <span class="dm-task-count">活跃: <span id="dm-count-active">0</span> 等待: <span id="dm-count-wait">0</span></span>
      </div>

      <div class="dm-body" id="dm-task-list">
        <div class="dm-empty">暂无下载任务</div>
      </div>

      <div class="dm-footer">
        <button class="dm-btn dm-btn-primary" id="dm-new-task">+ 新建下载</button>
      </div>
    `;

    document.body.appendChild(this.container);
    this.bindEvents();
  }

  // ---------- 绑定事件 ----------
  private bindEvents(): void {
    this.container?.querySelector('#dm-close')?.addEventListener('click', () => this.hide());
    this.container?.querySelector('#dm-add')?.addEventListener('click', () => this.showNewTaskDialog());
    this.container?.querySelector('#dm-new-task')?.addEventListener('click', () => this.showNewTaskDialog());
    this.container?.querySelector('#dm-pause-all')?.addEventListener('click', async () => {
      await this.rpc.pauseAll();
      this.refresh();
    });
    this.container?.querySelector('#dm-resume-all')?.addEventListener('click', async () => {
      await this.rpc.resumeAll();
      this.refresh();
    });
  }

  // ---------- 新建下载对话框 ----------
  private showNewTaskDialog(): void {
    const existing = document.getElementById('dm-new-dialog');
    if (existing) existing.remove();

    const dialog = document.createElement('div');
    dialog.id = 'dm-new-dialog';
    dialog.className = 'dm-dialog';
    dialog.innerHTML = `
      <div class="dm-dialog-content">
        <div class="dm-dialog-header">
          <span>新建下载</span>
          <button class="dm-btn-close" id="dm-dialog-close">✕</button>
        </div>
        <div class="dm-dialog-body">
          <div class="dm-input-group">
            <label>下载链接 / 磁力链接</label>
            <input type="text" id="dm-input-url" placeholder="https://... 或 magnet:?xt=..." autofocus>
          </div>
          <div class="dm-input-group">
            <label>保存文件名（可选）</label>
            <input type="text" id="dm-input-name" placeholder="自动识别">
          </div>
          <div class="dm-input-group">
            <label>保存目录（可选）</label>
            <input type="text" id="dm-input-dir" placeholder="默认下载目录">
          </div>
        </div>
        <div class="dm-dialog-footer">
          <button class="dm-btn dm-btn-primary" id="dm-dialog-submit">开始下载</button>
          <button class="dm-btn" id="dm-dialog-cancel">取消</button>
        </div>
      </div>
    `;

    this.container?.appendChild(dialog);

    const urlInput = dialog.querySelector('#dm-input-url') as HTMLInputElement;
    urlInput.focus();

    dialog.querySelector('#dm-dialog-close')?.addEventListener('click', () => dialog.remove());
    dialog.querySelector('#dm-dialog-cancel')?.addEventListener('click', () => dialog.remove());
    dialog.querySelector('#dm-dialog-submit')?.addEventListener('click', async () => {
      const url = urlInput.value.trim();
      if (!url) return;

      const name = (dialog.querySelector('#dm-input-name') as HTMLInputElement).value.trim();
      const dir = (dialog.querySelector('#dm-input-dir') as HTMLInputElement).value.trim();

      try {
        const options: any = {};
        if (name) options.out = name;
        if (dir) options.dir = dir;

        if (url.startsWith('magnet:')) {
          await this.rpc.addMagnet(url, options);
        } else {
          await this.rpc.addUri(url, options);
        }

        dialog.remove();
        this.refresh();
      } catch (err) {
        alert(`添加失败: ${err}`);
      }
    });

    // Enter 键提交
    urlInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        dialog.querySelector<HTMLButtonElement>('#dm-dialog-submit')?.click();
      }
    });
  }

  // ---------- 刷新数据 ----------
  async refresh(): Promise<void> {
    try {
      const [active, waiting, stopped, stat] = await Promise.all([
        this.rpc.getActive(),
        this.rpc.getWaiting(),
        this.rpc.getStopped(),
        this.rpc.getGlobalStat(),
      ]);

      this.currentTasks = {
        active: active.map(formatTask),
        waiting: waiting.map(formatTask),
        stopped: stopped.slice(0, 20).map(formatTask),
      };

      // 更新速度
      const speedDown = this.container?.querySelector('#dm-speed-down');
      const speedUp = this.container?.querySelector('#dm-speed-up');
      const countActive = this.container?.querySelector('#dm-count-active');
      const countWait = this.container?.querySelector('#dm-count-wait');

      if (speedDown) speedDown.textContent = humanSize(parseInt(stat.downloadSpeed || '0')) + '/s';
      if (speedUp) speedUp.textContent = humanSize(parseInt(stat.uploadSpeed || '0')) + '/s';
      if (countActive) countActive.textContent = stat.numActive || '0';
      if (countWait) countWait.textContent = stat.numWaiting || '0';

      // 更新任务列表
      this.renderTasks();
    } catch {
      // Aria2 未运行
      const list = this.container?.querySelector('#dm-task-list');
      if (list) list.innerHTML = '<div class="dm-empty">Aria2 未启动。点击下方按钮启动。</div>';
    }
  }

  // ---------- 渲染任务列表 ----------
  private renderTasks(): void {
    const list = this.container?.querySelector('#dm-task-list');
    if (!list) return;

    const { active, waiting, stopped } = this.currentTasks;

    if (active.length === 0 && waiting.length === 0 && stopped.length === 0) {
      list.innerHTML = '<div class="dm-empty">暂无下载任务</div>';
      return;
    }

    let html = '';

    // 活跃任务
    for (const task of active) {
      html += this.renderActiveTask(task);
    }

    // 等待任务
    for (const task of waiting) {
      html += this.renderWaitingTask(task);
    }

    // 已完成任务
    if (stopped.length > 0) {
      html += '<div class="dm-section-title">已完成</div>';
      for (const task of stopped) {
        html += this.renderStoppedTask(task);
      }
    }

    list.innerHTML = html;

    // 绑定任务操作按钮
    list.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const action = (e.target as HTMLElement).dataset.action;
        const gid = (e.target as HTMLElement).dataset.gid;
        if (!action || !gid) return;

        if (action === 'pause') await this.rpc.pause(gid);
        if (action === 'resume') await this.rpc.resume(gid);
        if (action === 'remove') await this.rpc.remove(gid);

        this.refresh();
      });
    });
  }

  private renderActiveTask(task: DownloadTask): string {
    return `
      <div class="dm-task dm-task-active">
        <div class="dm-task-info">
          <div class="dm-task-name">${this.escapeHtml(task.filename)}</div>
          <div class="dm-task-meta">
            <span>${task.completed_human} / ${task.total_human}</span>
            <span class="dm-task-speed">${task.speed_human}</span>
            <span>剩余 ${task.remaining_human}</span>
            <span>${task.connections} 连接</span>
          </div>
        </div>
        <div class="dm-progress-bar">
          <div class="dm-progress-fill" style="width: ${task.progress}%"></div>
          <span class="dm-progress-text">${task.progress}%</span>
        </div>
        <div class="dm-task-actions">
          <button class="dm-btn-icon" data-action="pause" data-gid="${task.gid}" title="暂停">⏸</button>
          <button class="dm-btn-icon" data-action="remove" data-gid="${task.gid}" title="删除">✕</button>
        </div>
      </div>
    `;
  }

  private renderWaitingTask(task: DownloadTask): string {
    return `
      <div class="dm-task dm-task-waiting">
        <div class="dm-task-info">
          <div class="dm-task-name">${this.escapeHtml(task.filename || task.gid)}</div>
          <div class="dm-task-meta">
            <span>${task.total_human}</span>
            <span>等待中</span>
          </div>
        </div>
        <div class="dm-task-actions">
          <button class="dm-btn-icon" data-action="resume" data-gid="${task.gid}" title="开始">▶</button>
          <button class="dm-btn-icon" data-action="remove" data-gid="${task.gid}" title="删除">✕</button>
        </div>
      </div>
    `;
  }

  private renderStoppedTask(task: DownloadTask): string {
    const isComplete = task.status === 'complete';
    const statusIcon = isComplete ? '✅' : '❌';
    const statusText = isComplete ? task.total_human : (task.error_message || '出错');

    return `
      <div class="dm-task dm-task-stopped ${isComplete ? 'dm-task-complete' : 'dm-task-error'}">
        <div class="dm-task-info">
          <div class="dm-task-name">${statusIcon} ${this.escapeHtml(task.filename)}</div>
          <div class="dm-task-meta">
            <span>${statusText}</span>
          </div>
        </div>
        <div class="dm-task-actions">
          <button class="dm-btn-icon" data-action="remove" data-gid="${task.gid}" title="删除">✕</button>
        </div>
      </div>
    `;
  }

  // ---------- 轮询 ----------
  private startPolling(): void {
    this.pollTimer = setInterval(() => {
      if (this.isVisible) this.refresh();
    }, 1000);
  }

  // ---------- 工具 ----------
  private escapeHtml(str: string): string {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // ---------- 样式注入 ----------
  private injectStyles(): void {
    if (document.getElementById('butler-download-styles')) return;
    const style = document.createElement('style');
    style.id = 'butler-download-styles';
    style.textContent = STYLES;
    document.head.appendChild(style);
  }
}

// ============================================================
// 样式
// ============================================================

const STYLES = `
#butler-download-manager {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 600px;
  max-height: 80vh;
  z-index: 999999;
  display: none;
  flex-direction: column;
  background: rgba(30, 30, 40, 0.92);
  backdrop-filter: blur(24px) saturate(1.4);
  -webkit-backdrop-filter: blur(24px) saturate(1.4);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  box-shadow: 0 16px 64px rgba(0, 0, 0, 0.5);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: #e0e0e0;
  overflow: hidden;
  animation: dm-slideIn 0.2s ease;
}

@keyframes dm-slideIn {
  from { opacity: 0; transform: translate(-50%, -50%) scale(0.95); }
  to   { opacity: 1; transform: translate(-50%, -50%) scale(1); }
}

/* 头部 */
.dm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.dm-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
}

.dm-icon { font-size: 20px; }

.dm-header-actions {
  display: flex;
  gap: 6px;
}

/* 速度栏 */
.dm-speed-bar {
  display: flex;
  gap: 16px;
  padding: 8px 18px;
  font-size: 12px;
  color: #888;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.dm-speed-down { color: #4a9eff; }
.dm-speed-up { color: #66bb6a; }
.dm-task-count { margin-left: auto; }

/* 任务列表 */
.dm-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  min-height: 200px;
  max-height: 50vh;
}

.dm-empty {
  text-align: center;
  padding: 40px 20px;
  color: #666;
  font-size: 14px;
}

.dm-section-title {
  padding: 8px 10px 4px;
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 任务卡片 */
.dm-task {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  margin-bottom: 4px;
  transition: background 0.15s;
}

.dm-task:hover { background: rgba(255, 255, 255, 0.04); }

.dm-task-info { flex: 1; min-width: 0; }

.dm-task-name {
  font-size: 13px;
  font-weight: 600;
  color: #f0f0f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dm-task-meta {
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: #888;
  margin-top: 3px;
}

.dm-task-speed { color: #4a9eff; }

/* 进度条 */
.dm-progress-bar {
  position: relative;
  flex: 0 0 120px;
  height: 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
  overflow: hidden;
}

.dm-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4a9eff, #1a6dd4);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.dm-progress-text {
  position: absolute;
  right: 0;
  top: -16px;
  font-size: 10px;
  color: #aaa;
}

/* 任务操作 */
.dm-task-actions {
  display: flex;
  gap: 4px;
}

/* 底部 */
.dm-footer {
  padding: 12px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  justify-content: center;
}

/* 按钮 */
.dm-btn {
  padding: 6px 14px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  color: #ddd;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}

.dm-btn:hover { background: rgba(255, 255, 255, 0.12); }

.dm-btn-primary {
  background: linear-gradient(135deg, #4a9eff, #1a6dd4);
  border: none;
  color: #fff;
  font-weight: 600;
}

.dm-btn-primary:hover { background: linear-gradient(135deg, #5aadff, #2a7de4); }

.dm-btn-sm {
  width: 30px;
  height: 30px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  border-radius: 8px;
}

.dm-btn-close { font-size: 16px; color: #999; }

.dm-btn-icon {
  width: 28px;
  height: 28px;
  border: none;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  color: #aaa;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.dm-btn-icon:hover { background: rgba(255, 255, 255, 0.15); color: #fff; }

/* 对话框 */
.dm-dialog {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(20, 20, 30, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  border-radius: 16px;
}

.dm-dialog-content {
  width: 85%;
  background: rgba(40, 40, 55, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  overflow: hidden;
}

.dm-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-weight: 700;
  color: #fff;
}

.dm-dialog-body { padding: 16px; }

.dm-input-group {
  margin-bottom: 12px;
}

.dm-input-group label {
  display: block;
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}

.dm-input-group input {
  width: 100%;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: #f0f0f0;
  font-size: 13px;
  outline: none;
  box-sizing: border-box;
}

.dm-input-group input:focus {
  border-color: #4a9eff;
  background: rgba(255, 255, 255, 0.08);
}

.dm-input-group input::placeholder { color: #555; }

.dm-dialog-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

/* 完成/错误状态 */
.dm-task-complete .dm-task-name { color: #66bb6a; }
.dm-task-error .dm-task-name { color: #ef5350; }
`;

// ============================================================
// 导出
// ============================================================

const downloadManager = new DownloadManagerUI();

export { downloadManager, DownloadManagerUI };
