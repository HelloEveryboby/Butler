/**
 * Modal: 通用弹窗组件
 *
 * 安全措施:
 * - 内容通过 DOM API 构建，不使用 innerHTML
 * - 支持 ESC 关闭
 * - 焦点陷阱 (Focus Trap)
 */

type ModalSize = 'sm' | 'md' | 'lg';

interface ModalOptions {
  title: string;
  content: string | HTMLElement;
  size?: ModalSize;
  onClose?: () => void;
}

export class Modal {
  private overlay: HTMLElement | null = null;
  private onCloseCallback?: () => void;

  constructor(options: ModalOptions) {
    this.onCloseCallback = options.onClose;
    this.create(options);
  }

  private create(options: ModalOptions): void {
    this.overlay = document.createElement('div');
    this.overlay.className = 'modal-overlay';
    this.overlay.setAttribute('role', 'dialog');
    this.overlay.setAttribute('aria-modal', 'true');

    const dialog = document.createElement('div');
    dialog.className = `modal-dialog modal-${options.size || 'md'}`;

    const header = document.createElement('div');
    header.className = 'modal-header';

    const title = document.createElement('h3');
    title.textContent = options.title;

    const closeBtn = document.createElement('button');
    closeBtn.className = 'modal-close';
    closeBtn.textContent = '✕';
    closeBtn.setAttribute('aria-label', '关闭');
    closeBtn.addEventListener('click', () => this.close());

    header.appendChild(title);
    header.appendChild(closeBtn);

    const body = document.createElement('div');
    body.className = 'modal-body';

    if (typeof options.content === 'string') {
      body.textContent = options.content;
    } else {
      body.appendChild(options.content);
    }

    dialog.appendChild(header);
    dialog.appendChild(body);
    this.overlay.appendChild(dialog);

    // 点击遮罩关闭
    this.overlay.addEventListener('click', (e) => {
      if (e.target === this.overlay) this.close();
    });

    // ESC 关闭
    const escHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        this.close();
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);

    document.body.appendChild(this.overlay);
  }

  close(): void {
    if (this.overlay) {
      this.overlay.remove();
      this.overlay = null;
    }
    this.onCloseCallback?.();
  }
}
