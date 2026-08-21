/**
 * General-purpose Modal Component (GitHub Copilot Style)
 */

interface ModalShowOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  onConfirm?: () => void;
  onCancel?: () => void;
  triggerBtn?: HTMLElement;
}

class CopilotModal {
  public modal: HTMLElement | null;
  public titleEl: HTMLElement | null = null;
  public bodyEl: HTMLElement | null = null;
  public allowBtn: HTMLElement | null = null;
  public dismissBtn: HTMLElement | null = null;
  public triggerBtn: HTMLElement | null = null;

  public onConfirm: (() => void) | null = null;
  public onCancel: (() => void) | null = null;

  constructor(modalId: string = 'copilot-modal') {
    this.modal = document.getElementById(modalId);
    if (!this.modal) {
      console.error(`Modal element with id ${modalId} not found.`);
      return;
    }

    this.titleEl = this.modal.querySelector('.modal-title');
    this.bodyEl = this.modal.querySelector('.modal-body-text');
    this.allowBtn = this.modal.querySelector('.modal-btn-allow');
    this.dismissBtn = this.modal.querySelector('.modal-btn-dismiss');

    this.initEvents();
  }

  public initEvents(): void {
    if (!this.modal) return;

    this.dismissBtn?.addEventListener('click', () => this.close());

    this.modal.addEventListener('click', (e: MouseEvent) => {
      if (e.target === this.modal) {
        this.close();
      }
    });

    this.allowBtn?.addEventListener('click', () => {
      if (this.onConfirm) this.onConfirm();
      this.close();
    });

    window.addEventListener('keydown', (e: KeyboardEvent) => {
      if (!this.modal?.classList.contains('show-modal')) return;

      if (e.key === 'Escape') {
        this.close();
      }

      if (e.key === 'Tab') {
        this.handleFocusTrap(e);
      }
    });
  }

  public show({
    title,
    message,
    confirmText = '允许',
    cancelText = '解雇',
    onConfirm,
    onCancel,
    triggerBtn,
  }: ModalShowOptions): void {
    if (!this.modal) return;

    if (this.titleEl) this.titleEl.innerText = title;
    if (this.bodyEl) this.bodyEl.innerText = message;
    if (this.allowBtn) this.allowBtn.innerText = confirmText;
    if (this.dismissBtn) this.dismissBtn.innerText = cancelText;

    this.onConfirm = onConfirm || null;
    this.onCancel = onCancel || null;
    this.triggerBtn = triggerBtn || null;

    this.modal.classList.add('show-modal');
    document.body.classList.add('modal-open');

    setTimeout(() => {
      this.allowBtn?.focus();
    }, 100);
  }

  public close(): void {
    if (!this.modal) return;
    this.modal.classList.remove('show-modal');
    document.body.classList.remove('modal-open');
    if (this.onCancel) this.onCancel();

    if (this.triggerBtn) {
      this.triggerBtn.focus();
    }
  }

  public handleFocusTrap(e: KeyboardEvent): void {
    if (!this.allowBtn || !this.dismissBtn) return;
    const focusableElements = [this.allowBtn, this.dismissBtn];
    const firstFocusable = focusableElements[0];
    const lastFocusable = focusableElements[focusableElements.length - 1];

    if (e.shiftKey) {
      if (document.activeElement === firstFocusable) {
        lastFocusable.focus();
        e.preventDefault();
      }
    } else {
      if (document.activeElement === lastFocusable) {
        firstFocusable.focus();
        e.preventDefault();
      }
    }
  }
}

if (typeof window !== 'undefined') {
  (window as any).CopilotModal = CopilotModal;
  window.modalManager = new CopilotModal();
}
