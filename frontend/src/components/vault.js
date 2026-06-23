class VaultCompartment {
    constructor() {
        this.vaultCard = null;
        this.isLocked = true;
        this.init();
    }

    init() {
        // Create Vault Card in Skills Quadrant (1,1)
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
                    <button class="apple-btn-primary" onclick="vault.unlock()">解锁</button>
                </div>
            `;
            skillsDrawer.prepend(this.vaultCard);
        }
    }

    async unlock() {
        const pwd = document.getElementById('vault-master-pwd').value;
        if (window.pywebview && window.pywebview.api) {
            // Mocking unlock success for demo, in reality call backend
            // const success = await window.pywebview.api.unlock_vault(pwd);
            const success = true;

            if (success) {
                this.vaultCard.classList.add('vault-open');
                this.vaultCard.querySelector('.vault-lock-animation i').className = 'fas fa-lock-open';
                this.vaultCard.querySelector('.vault-unlock-overlay').style.display = 'none';
                this.vaultCard.querySelector('.vault-content').style.display = 'block';
                this.isLocked = false;
                this.renderKeys();

                // Sound effect (placeholder)
                console.log("Vault Unlocked: Click!");
            }
        }
    }

    renderKeys() {
        const container = document.getElementById('vault-keys');
        const keys = ['OPENAI_API_KEY', 'DEEPSEEK_KEY', 'AWS_SECRET'];

        container.innerHTML = keys.map(key => `
            <div class="credential-item" style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">
                <div class="credential-key" draggable="true" data-key-id="${key}" ondragstart="vault.onKeyDragStart(event)"></div>
                <div style="font-size: 13px; color: #d4af37;">${key}</div>
            </div>
        `).join('');
    }

    onKeyDragStart(e) {
        e.dataTransfer.setData('application/butler-key', e.target.dataset.keyId);
        e.target.classList.add('dragging');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.vault = new VaultCompartment();
});
