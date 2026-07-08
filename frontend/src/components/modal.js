/**
 * General-purpose Modal Component (GitHub Copilot Style)
 */
class CopilotModal {
    constructor(modalId = 'copilot-modal') {
        this.modal = document.getElementById(modalId);
        if (!this.modal) {
            console.error(`Modal element with id ${modalId} not found.`);
            return;
        }

        this.titleEl = this.modal.querySelector('.modal-title');
        this.bodyEl = this.modal.querySelector('.modal-body-text');
        this.allowBtn = this.modal.querySelector('.modal-btn-allow');
        this.dismissBtn = this.modal.querySelector('.modal-btn-dismiss');
        this.triggerBtn = null; // To return focus

        this.onConfirm = null;
        this.onCancel = null;

        this.initEvents();
    }

    initEvents() {
        // Dismiss on click
        this.dismissBtn.addEventListener('click', () => this.close());

        // Backdrop click
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close();
            }
        });

        // Allow click
        this.allowBtn.addEventListener('click', () => {
            if (this.onConfirm) this.onConfirm();
            this.close();
        });

        // Keyboard events
        window.addEventListener('keydown', (e) => {
            if (!this.modal.classList.contains('show-modal')) return;

            if (e.key === 'Escape') {
                this.close();
            }

            if (e.key === 'Tab') {
                this.handleFocusTrap(e);
            }
        });
    }

    show({ title, message, confirmText = '允许', cancelText = '解雇', onConfirm, onCancel, triggerBtn }) {
        if (this.titleEl) this.titleEl.innerText = title;
        if (this.bodyEl) this.bodyEl.innerText = message;
        if (this.allowBtn) this.allowBtn.innerText = confirmText;
        if (this.dismissBtn) this.dismissBtn.innerText = cancelText;

        this.onConfirm = onConfirm;
        this.onCancel = onCancel;
        this.triggerBtn = triggerBtn;

        this.modal.classList.add('show-modal');
        document.body.classList.add('modal-open'); // For scroll locking

        // Focus first button (Allow)
        setTimeout(() => {
            this.allowBtn.focus();
        }, 100);
    }

    close() {
        this.modal.classList.remove('show-modal');
        document.body.classList.remove('modal-open');
        if (this.onCancel) this.onCancel();

        // Return focus
        if (this.triggerBtn) {
            this.triggerBtn.focus();
        }
    }

    handleFocusTrap(e) {
        const focusableElements = [this.allowBtn, this.dismissBtn];
        const firstFocusable = focusableElements[0];
        const lastFocusable = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) { // Tab + Shift
            if (document.activeElement === firstFocusable) {
                lastFocusable.focus();
                e.preventDefault();
            }
        } else { // Tab
            if (document.activeElement === lastFocusable) {
                firstFocusable.focus();
                e.preventDefault();
            }
        }
    }
}

// Export to window
window.CopilotModal = CopilotModal;
