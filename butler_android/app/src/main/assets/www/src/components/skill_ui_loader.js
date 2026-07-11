document.addEventListener('DOMContentLoaded', () => {
    const drawer = document.getElementById('skills-drawer');
    if (!drawer) return;

    // Default built-in mock skills (translated beautifully to Chinese matching the theme)
    const baseMockSkills = [
        { name: '截图排障', icon: 'fa-bug', color: '#FF3B30' },
        { name: '局域网同步', icon: 'fa-sync', color: '#34C759' },
        { name: '系统清理', icon: 'fa-broom', color: '#FF9500' }
    ];

    async function initSkillsList() {
        let uiSkills = [];
        const isMockMode = typeof window.pywebview === 'undefined' || typeof window.pywebview.api === 'undefined';

        if (!isMockMode) {
            try {
                // Fetch dynamic skills from the Python SkillManager via ModernBridge
                uiSkills = await window.pywebview.api.get_ui_skills();
            } catch (err) {
                console.error("Failed to query real UI skills from backend", err);
            }
        } else {
            // Local fallback mock mode: Include Storage Hub in browser preview
            uiSkills = [{
                id: "storage_hub",
                name: "存储中心",
                icon: "fa-box-open",
                frontend_path: "skills/storage_hub/ui/index.html"
            }];
        }

        // Clear hardcoded nodes from drawer
        drawer.innerHTML = '';

        // 1. Render default mock base skills
        baseMockSkills.forEach(skill => {
            const card = document.createElement('div');
            card.className = 'dag-node glass-surface';
            card.draggable = true;
            card.style.position = 'relative';
            card.style.marginBottom = '10px';
            card.innerHTML = `<i class="fas ${skill.icon}" style="color: ${skill.color}"></i> <span>${skill.name}</span>`;

            card.ondragstart = (e) => {
                e.dataTransfer.setData('application/json', JSON.stringify({
                    type: 'skill',
                    name: skill.name,
                    icon: skill.icon
                }));
            };
            drawer.appendChild(card);
        });

        // 2. Render dynamic live UI skills
        uiSkills.forEach(skill => {
            const card = document.createElement('div');
            card.className = 'dag-node glass-surface live-ui-skill-card';
            card.draggable = true;
            card.style.position = 'relative';
            card.style.marginBottom = '10px';
            card.style.border = '1px solid rgba(45, 164, 78, 0.3)';
            card.style.boxShadow = '0 0 8px rgba(45, 164, 78, 0.1)';

            // Premium green glowing indicator for interactive skills
            card.innerHTML = `
                <i class="fas ${skill.icon || 'fa-folder-open'}" style="color: #2da44e"></i>
                <span>${skill.name === 'Storage Hub' ? '存储中心' : skill.name}</span>
                <span style="position: absolute; right: 10px; font-size: 8px; background: rgba(45,164,78,0.2); color: #2da44e; padding: 2px 5px; border-radius: 4px; font-weight: 700; text-transform: uppercase;">UI</span>
            `;

            // Click navigates internally inside Webview via custom ModernBridge method
            card.onclick = async () => {
                if (isMockMode) {
                    // Browser standalone simulation fallback
                    window.location.href = skill.frontend_path;
                } else {
                    try {
                        window.showToast("载入组件", `正在跳转至 ${skill.name === 'Storage Hub' ? '存储中心' : skill.name}...`, "success");
                        await window.pywebview.api.load_skill_frontend(skill.frontend_path);
                    } catch (err) {
                        console.error("Navigation call failed", err);
                        window.showToast("路由错误", "无法在 webview 容器内加载该页面", "error");
                    }
                }
            };

            card.ondragstart = (e) => {
                e.dataTransfer.setData('application/json', JSON.stringify({
                    type: 'skill',
                    name: skill.name,
                    id: skill.id,
                    is_ui: true,
                    frontend_path: skill.frontend_path
                }));
            };

            drawer.appendChild(card);
        });
    }

    // Wait slightly to let main.js clean up or load first
    setTimeout(initSkillsList, 100);
});
