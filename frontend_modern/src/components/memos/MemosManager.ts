/**
 * MemosManager: 备忘录系统
 *
 * 管理本地备忘录的增删改查。
 */

import { bridge } from '@/api';
import { toast } from '@/utils/toast';
import { escapeHTML } from '@/utils/escape';

interface Memo {
  id: string;
  title: string;
  content: string;
  createdAt: number;
  updatedAt: number;
}

export class MemosManager {
  private container: HTMLElement | null = null;
  private memos: Memo[] = [];

  constructor(containerId = 'memos-content') {
    this.container = document.getElementById(containerId);
    if (this.container) {
      this.loadMemos();
    }
  }

  private async loadMemos(): Promise<void> {
    try {
      const data = await bridge.callSkill('memos', 'list');
      if (Array.isArray(data)) {
        this.memos = data;
        this.render();
      }
    } catch {
      toast.warning('备忘录', '无法加载备忘录列表');
    }
  }

  private render(): void {
    if (!this.container) return;
    this.container.innerHTML = '';

    if (this.memos.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'glass-card text-muted text-center';
      empty.textContent = '暂无备忘录';
      this.container.appendChild(empty);
      return;
    }

    for (const memo of this.memos) {
      const card = document.createElement('div');
      card.className = 'glass-card memo-card';

      const title = document.createElement('div');
      title.className = 'font-bold';
      title.textContent = memo.title;

      const preview = document.createElement('div');
      preview.className = 'text-muted text-sm text-truncate';
      preview.textContent = memo.content.substring(0, 100);

      const time = document.createElement('div');
      time.className = 'text-muted text-xs';
      time.textContent = new Date(memo.updatedAt).toLocaleString();

      card.appendChild(title);
      card.appendChild(preview);
      card.appendChild(time);

      card.addEventListener('click', () => {
        window.openEditor?.(memo.content, memo.title);
      });

      this.container.appendChild(card);
    }
  }

  async create(title: string, content: string): Promise<void> {
    try {
      await bridge.callSkill('memos', 'create', { title, content });
      toast.success('备忘录', '创建成功');
      await this.loadMemos();
    } catch {
      toast.error('备忘录', '创建失败');
    }
  }
}
