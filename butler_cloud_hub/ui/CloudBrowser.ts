"""
CloudHub 前端 UI 组件

通过 pywebview.api.cloud_xxx() 调用后端，
在 Butler 的 2x2 矩阵中展示统一文件浏览器。
"""

import { toast } from '@/utils/toast';
import { escapeHTML } from '@/utils/escape';

interface FileItem {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
  modified: string | null;
  mime_type: string | null;
  storage?: string;
}

interface StorageInfo {
  name: string;
  type: string;
  connected: boolean;
  read_only: boolean;
}

/**
 * CloudHub 文件浏览器
 *
 * 嵌入 Butler 前端，通过 pywebview 直接调用 Python。
 */
export class CloudBrowser {
  private container: HTMLElement | null = null;
  private currentStorage = '';
  private currentPath = '/';
  private storages: StorageInfo[] = [];
  private files: FileItem[] = [];

  constructor(containerId = 'cloud-content') {
    this.container = document.getElementById(containerId);
    if (this.container) {
      this.render();
      this.loadStorages();
    }
  }

  private get api(): any {
    return (window as any).pywebview?.api;
  }

  private render(): void {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="cloud-header">
        <select id="cloud-storage-select" class="glass-input" style="max-width:200px"></select>
        <button id="cloud-back-btn" class="glass-btn" style="display:none">← 返回</button>
        <div id="cloud-breadcrumb" class="font-mono text-sm text-muted" style="flex:1;text-align:center"></div>
      </div>
      <div id="cloud-file-list" class="cloud-file-list"></div>
    `;

    document.getElementById('cloud-storage-select')?.addEventListener('change', (e) => {
      this.currentStorage = (e.target as HTMLSelectElement).value;
      this.currentPath = '/';
      this.loadFiles();
    });

    document.getElementById('cloud-back-btn')?.addEventListener('click', () => {
      const parent = this.currentPath.split('/').slice(0, -1).join('/') || '/';
      this.currentPath = parent;
      this.loadFiles();
    });
  }

  private async loadStorages(): Promise<void> {
    try {
      const raw = this.api?.cloud_list_storages?.();
      if (!raw) return;
      this.storages = JSON.parse(raw);

      const select = document.getElementById('cloud-storage-select') as HTMLSelectElement;
      if (select && this.storages.length > 0) {
        select.innerHTML = this.storages.map(s =>
          `<option value="${escapeHTML(s.name)}">${escapeHTML(s.name)} (${s.type})</option>`
        ).join('');
        this.currentStorage = this.storages[0].name;
        this.loadFiles();
      }
    } catch (e) {
      toast.warning('CloudHub', '无法加载存储列表');
    }
  }

  private async loadFiles(): Promise<void> {
    try {
      const raw = this.api?.cloud_list_files?.(this.currentStorage, this.currentPath);
      if (!raw) return;
      const data = JSON.parse(raw);

      if (data.status === 'error') {
        toast.error('CloudHub', data.message);
        return;
      }

      this.files = data.files || [];
      this.renderFiles();
    } catch (e) {
      toast.warning('CloudHub', '无法加载文件列表');
    }
  }

  private renderFiles(): void {
    const list = document.getElementById('cloud-file-list');
    const breadcrumb = document.getElementById('cloud-breadcrumb');
    const backBtn = document.getElementById('cloud-back-btn');
    if (!list) return;

    // 面包屑
    if (breadcrumb) {
      breadcrumb.textContent = `${this.currentStorage}:${this.currentPath}`;
    }

    // 返回按钮
    if (backBtn) {
      backBtn.style.display = this.currentPath === '/' ? 'none' : '';
    }

    if (this.files.length === 0) {
      list.innerHTML = '<div class="glass-card text-muted text-center" style="padding:40px">📂 空目录</div>';
      return;
    }

    // 目录在前，按名称排序
    const sorted = [...this.files].sort((a, b) => {
      if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });

    list.innerHTML = '';
    for (const file of sorted) {
      const card = document.createElement('div');
      card.className = 'glass-card cloud-file-item';
      card.style.cssText = 'display:flex;align-items:center;gap:12px;padding:12px 16px;margin-bottom:8px;cursor:pointer;';

      const icon = file.is_dir ? '📁' : this.fileIcon(file.mime_type);
      const size = file.is_dir ? '' : this.formatSize(file.size);
      const time = file.modified ? new Date(file.modified).toLocaleDateString() : '';

      card.innerHTML = `
        <span style="font-size:24px;flex-shrink:0">${icon}</span>
        <div style="flex:1;min-width:0">
          <div class="text-truncate" style="font-weight:500">${escapeHTML(file.name)}</div>
          <div class="text-muted text-xs">${size} ${time}</div>
        </div>
        ${file.storage ? `<span class="text-muted text-xs">${escapeHTML(file.storage)}</span>` : ''}
      `;

      card.addEventListener('click', () => {
        if (file.is_dir) {
          this.currentPath = file.path;
          this.loadFiles();
        } else {
          toast.info('文件', `${file.name} (${this.formatSize(file.size)})`);
        }
      });

      list.appendChild(card);
    }
  }

  private fileIcon(mime: string | null): string {
    if (!mime) return '📄';
    if (mime.startsWith('image/')) return '🖼️';
    if (mime.startsWith('video/')) return '🎬';
    if (mime.startsWith('audio/')) return '🎵';
    if (mime.includes('pdf')) return '📕';
    if (mime.includes('zip') || mime.includes('rar')) return '📦';
    if (mime.includes('text') || mime.includes('json')) return '📝';
    return '📄';
  }

  private formatSize(bytes: number): string {
    if (bytes === 0) return '';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
  }
}
