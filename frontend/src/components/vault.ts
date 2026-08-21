/**
 * Butler Vault Compartment: Key storage and unlock UI.
 */

class VaultCompartment {
  public vaultCard: HTMLElement | null = null;
  public isLocked: boolean = true;

  constructor() {
    this.init();
  }

  public init(): void {
    const skillsDrawer = document.getElementById('skills-drawer');
    if (skillsDrawer) {
      this.vaultCard = document.createElement('div');
      this.vaultCard.className = 'vault-card glass-surface damping-transition';
      this.vaultCard.innerHTML = `
        <div class="view-header">
          <div class="view-title" style="color: #d4af37;"><i class="fas fa-shield-halved"></i> 安全密室</div>
          <div class="vault-lock-animation"><i class="fas fa-lock"></i></div>
        </div>
        <div class="vault-content" style="padding: 20px; display: none;">
          <div class="credentials-list" id="vault-keys">
            <!-- Keys will be rendered here -->
          </div>
        </div>
        <div class="vault-unlock-overlay" style="padding: 20px; text-align: center;">
          <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 12px;">请输入主密码解锁密室</p>
          <input type="password" id="vault-master-pwd" class="apple-select" style="width: 80%; margin-bottom: 12px;">
          <button class="apple-btn-primary" onclick="window.vault.unlock()">解锁</button>
        </div>
      `;
      skillsDrawer.prepend(this.vaultCard);
    }
  }

  public async unlock(): Promise<void> {
    const pwdInput = document.getElementById('vault-master-pwd') as HTMLInputElement;
    if (!pwdInput || !this.vaultCard) return;

    const success = true;

    if (success) {
      this.vaultCard.classList.add('vault-open');
      const lockIcon = this.vaultCard.querySelector('.vault-lock-animation i');
      if (lockIcon) lockIcon.className = 'fas fa-lock-open';

      const overlay = this.vaultCard.querySelector('.vault-unlock-overlay') as HTMLElement;
      if (overlay) overlay.style.display = 'none';

      const content = this.vaultCard.querySelector('.vault-content') as HTMLElement;
      if (content) content.style.display = 'block';

      this.isLocked = false;
      this.renderKeys();

      console.log('Vault Unlocked: Click!');
    }
  }

  public renderKeys(): void {
    const container = document.getElementById('vault-keys');
    if (!container) return;
    const keys = ['OPENAI_API_KEY', 'DEEPSEEK_KEY', 'AWS_SECRET'];

    container.innerHTML = keys
      .map(
        (key) => `
        <div class="credential-item" style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">
          <div class="credential-key" draggable="true" data-key-id="${key}" ondragstart="window.vault.onKeyDragStart(event)"></div>
          <div style="font-size: 13px; color: #d4af37;">${key}</div>
        </div>
      `
      )
      .join('');
  }

  public onKeyDragStart(e: DragEvent): void {
    if (!e.dataTransfer || !e.target) return;
    const target = e.target as HTMLElement;
    e.dataTransfer.setData('application/butler-key', target.dataset.keyId || '');
    target.classList.add('dragging');
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    window.vault = new VaultCompartment();
    (window as any).VaultCompartment = VaultCompartment;
  });
}
