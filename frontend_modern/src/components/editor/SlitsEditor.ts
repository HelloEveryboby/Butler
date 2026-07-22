/**
 * SlitsEditor: 内置代码/文本编辑器
 *
 * 支持 Markdown 高亮、自动保存。
 */

import { escapeHTML } from '@/utils/escape';
import { toast } from '@/utils/toast';

interface EditorOptions {
  content: string;
  filename: string;
  onSave?: (content: string) => void;
  readOnly?: boolean;
}

export class SlitsEditor {
  private container: HTMLElement | null = null;
  private textarea: HTMLTextAreaElement | null = null;
  private filename: string;
  private onSaveCallback?: (content: string) => void;
  private autoSaveTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(options: EditorOptions) {
    this.filename = options.filename;
    this.onSaveCallback = options.onSave;
    this.create(options.content, options.readOnly);
  }

  private create(content: string, readOnly = false): void {
    this.container = document.createElement('div');
    this.container.className = 'editor-container glass-panel';

    const header = document.createElement('div');
    header.className = 'editor-header';

    const filenameEl = document.createElement('span');
    filenameEl.className = 'editor-filename font-mono text-sm';
    filenameEl.textContent = this.filename;

    const actions = document.createElement('div');
    actions.className = 'editor-actions';

    if (!readOnly) {
      const saveBtn = document.createElement('button');
      saveBtn.className = 'glass-btn text-sm';
      saveBtn.textContent = '💾 保存';
      saveBtn.addEventListener('click', () => this.save());
      actions.appendChild(saveBtn);
    }

    const closeBtn = document.createElement('button');
    closeBtn.className = 'glass-btn text-sm';
    closeBtn.textContent = '✕';
    closeBtn.addEventListener('click', () => this.close());
    actions.appendChild(closeBtn);

    header.appendChild(filenameEl);
    header.appendChild(actions);

    this.textarea = document.createElement('textarea');
    this.textarea.className = 'editor-textarea font-mono';
    this.textarea.value = content;
    this.textarea.readOnly = readOnly;
    this.textarea.spellcheck = false;
    this.textarea.setAttribute('aria-label', `编辑器: ${this.filename}`);

    // 自动保存 (防抖 2 秒)
    if (!readOnly) {
      this.textarea.addEventListener('input', () => {
        if (this.autoSaveTimer) clearTimeout(this.autoSaveTimer);
        this.autoSaveTimer = setTimeout(() => this.save(), 2000);
      });
    }

    // Tab 缩进
    this.textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        e.preventDefault();
        const start = this.textarea!.selectionStart;
        const end = this.textarea!.selectionEnd;
        this.textarea!.value =
          this.textarea!.value.substring(0, start) + '  ' + this.textarea!.value.substring(end);
        this.textarea!.selectionStart = this.textarea!.selectionEnd = start + 2;
      }
    });

    this.container.appendChild(header);
    this.container.appendChild(this.textarea);
    document.body.appendChild(this.container);
  }

  save(): void {
    if (!this.textarea) return;
    this.onSaveCallback?.(this.textarea.value);
    toast.info('编辑器', `${this.filename} 已保存`);
  }

  close(): void {
    if (this.autoSaveTimer) {
      clearTimeout(this.autoSaveTimer);
    }
    this.container?.remove();
    this.container = null;
  }

  getContent(): string {
    return this.textarea?.value ?? '';
  }
}
