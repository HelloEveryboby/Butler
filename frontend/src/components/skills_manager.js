class SkillsManagerController {
    constructor() {
        this.allSkills = [];
        this.currentFilter = 'all'; // 'all', 'builtin', 'external', 'security'
        this.searchQuery = '';
        this.grid = document.getElementById('skills-manager-grid');
    }

    async init() {
        await this.refreshSkills();
        this.render();
    }

    async refreshSkills() {
        const isMockMode = typeof window.pywebview === 'undefined' || typeof window.pywebview.api === 'undefined';
        if (!isMockMode) {
            try {
                this.allSkills = await window.pywebview.api.get_all_skills_detailed();
            } catch (err) {
                console.error("Failed to fetch detailed skills from backend:", err);
                this.loadMockSkills();
            }
        } else {
            this.loadMockSkills();
        }
    }

    loadMockSkills() {
        // High fidelity mock skills to simulate a perfect experience in browser preview
        this.allSkills = [
            {
                id: 'memos',
                name: 'Memos 备忘空间',
                description: '双模态全景 Timeline & 瀑布流自研多媒体备忘记录系统',
                is_builtin: true,
                is_core: false,
                risk: 'low',
                has_frontend: true,
                frontend_path: 'skills/memos/ui/index.html',
                version: '2.5.0',
                author: 'Butler Core Devs'
            },
            {
                id: 'downloader',
                name: '存储离线下载器',
                description: '支持独立与集群运行模式的多协议高能离线文件下载技能',
                is_builtin: true,
                is_core: false,
                risk: 'low',
                has_frontend: true,
                frontend_path: 'skills/downloader/ui/index.html',
                version: '2.0.1',
                author: 'Butler Core Devs'
            },
            {
                id: 'storage_hub',
                name: '存储中心 (Storage Hub)',
                description: '统一多端高安全分布式密码与敏感资产冷热隔离存储仓',
                is_builtin: true,
                is_core: false,
                risk: 'medium',
                has_frontend: true,
                frontend_path: 'skills/storage_hub/ui/index.html',
                version: '3.0.0',
                author: 'Butler Core Devs'
            },
            {
                id: 'clipboard_history',
                name: '剪切板加密监控',
                description: '后台静默高敏捕获物理系统剪贴板事件并提供 AES 加密落盘',
                is_builtin: true,
                is_core: true,
                risk: 'medium',
                has_python: true,
                version: '1.2.0',
                author: 'Butler Security'
            },
            {
                id: 'sys_cleaner',
                name: '系统垃圾一键清理',
                description: '多平台智能垃圾缓存扫描，极速安全删除无用冗余数据',
                is_builtin: true,
                is_core: false,
                risk: 'high',
                has_python: true,
                has_frontend: true,
                frontend_path: 'skills/sys_cleaner/index.html',
                version: '1.5.0',
                author: 'Butler Core Devs'
            },
            {
                id: 'daily_fashion_stylist',
                name: '智能每日穿搭助理',
                description: '第三方穿搭扩展。基于实时天气与服装库，提供专业 AI 时尚建议',
                is_builtin: false,
                is_core: false,
                risk: 'low',
                has_python: true,
                version: '1.0.0',
                author: 'Community Contrib'
            },
            {
                id: 'mobile-app-tester',
                name: '移动端全方位渗透套件',
                description: '高级第三方外部安全审计工具。涉及系统底层网络截获与沙箱注入等高风险调试。',
                is_builtin: false,
                is_core: false,
                risk: 'high',
                has_python: true,
                version: '0.9.4',
                author: 'Security Radar'
            }
        ];
    }

    setFilter(filterName) {
        this.currentFilter = filterName;
        document.querySelectorAll('.skills-nav-filter').forEach(btn => {
            if (btn.id === `filter-${filterName}`) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        this.render();
    }

    search(query) {
        this.searchQuery = query.toLowerCase().trim();
        this.render();
    }

    async installSkill() {
        const urlInput = document.getElementById('install-skill-url');
        const nameInput = document.getElementById('install-skill-name');
        const url = urlInput.value.trim();
        const name = nameInput.value.trim();

        if (!url) {
            window.showToast("缺少参数", "请输入需要导入/安装的技能 Git 仓库 URL 或本地物理路径。", "error");
            return;
        }

        window.showToast("正在部署", `开始安装外部插件 [${name || '未知'}]，正在执行 AST 静态安全性扫描与多端环境部署...`, "success");

        const isMockMode = typeof window.pywebview === 'undefined' || typeof window.pywebview.api === 'undefined';
        if (!isMockMode) {
            try {
                const res = await window.pywebview.api.install_skill(url, name || null);
                window.showToast("部署结果", res, res.includes("✅") ? "success" : "error");
                urlInput.value = '';
                nameInput.value = '';
                await this.refreshSkills();
                this.render();
            } catch (err) {
                console.error("Installation call failed:", err);
                window.showToast("部署失败", "后台安装任务发生未知网络或进程异常。", "error");
            }
        } else {
            // Mock installation delay
            setTimeout(() => {
                this.allSkills.push({
                    id: name.toLowerCase() || 'custom_skill',
                    name: name || '自定义导入外部技能',
                    description: `成功从外部资源 [${url}] 导入的安全技能。已通过 AST 安全审计验证并建立 Popen 独立隔离沙箱。`,
                    is_builtin: false,
                    is_core: false,
                    risk: 'low',
                    has_python: true,
                    version: '1.0.0',
                    author: 'External Developer'
                });
                urlInput.value = '';
                nameInput.value = '';
                window.showToast("部署成功", "🎉 外部扩展技能已成功导入！热插拔挂载成功，AI 大脑已实时更新技能树。", "success");
                this.render();
            }, 1800);
        }
    }

    async uninstallSkill(skillId, event) {
        if (event) event.stopPropagation();

        const isMockMode = typeof window.pywebview === 'undefined' || typeof window.pywebview.api === 'undefined';
        window.showToast("卸载中", `正在热卸载插件 [${skillId}]，安全清理磁盘碎片与缓存记录...`, "success");

        if (!isMockMode) {
            try {
                const res = await window.pywebview.api.uninstall_skill(skillId);
                window.showToast("卸载结果", res, res.includes("✅") ? "success" : "error");
                await this.refreshSkills();
                this.render();
            } catch (err) {
                console.error("Uninstallation call failed:", err);
                window.showToast("卸载失败", "后台卸载任务发生异常。", "error");
            }
        } else {
            setTimeout(() => {
                this.allSkills = this.allSkills.filter(s => s.id !== skillId);
                window.showToast("卸载完成", `外部扩展技能 [${skillId}] 已彻底从本地存储物理清除。`, "success");
                this.render();
            }, 1000);
        }
    }

    async openSkill(skill) {
        if (skill.has_frontend) {
            const isMockMode = typeof window.pywebview === 'undefined' || typeof window.pywebview.api === 'undefined';
            if (isMockMode) {
                window.showToast("跳转前端", `正在跳转至: ${skill.name} 专属微应用界面...`, "success");
                // Local simulation open overlay/iframe or redirect
                if (skill.id === 'memos') {
                    toggleSkillsManager();
                    window.toggleMemos();
                } else {
                    window.location.href = skill.frontend_path;
                }
            } else {
                try {
                    toggleSkillsManager();
                    window.showToast("加载应用", `正在唤醒 ${skill.name} 图形微应用控制台...`, "success");
                    await window.pywebview.api.load_skill_frontend(skill.frontend_path);
                } catch (err) {
                    console.error("Failed to load skill frontend:", err);
                    window.showToast("唤醒失败", "Webview 路由容器加载异常。", "error");
                }
            }
        } else {
            window.showToast("命令行唤醒", `已加载 Python 运行时环境，该技能可以通过 Smart Chat 意图自动协同调用。`, "success");
        }
    }

    render() {
        if (!this.grid) return;
        this.grid.innerHTML = '';

        // Filter and search
        let filtered = this.allSkills;

        if (this.currentFilter === 'builtin') {
            filtered = filtered.filter(s => s.is_builtin);
        } else if (this.currentFilter === 'external') {
            filtered = filtered.filter(s => !s.is_builtin);
        } else if (this.currentFilter === 'security') {
            // Emphasize security view, sort high risk first or filter non-low risk
            filtered = filtered.filter(s => s.risk !== 'low' || !s.is_builtin);
        }

        if (this.searchQuery) {
            filtered = filtered.filter(s =>
                s.name.toLowerCase().includes(this.searchQuery) ||
                s.description.toLowerCase().includes(this.searchQuery) ||
                s.id.toLowerCase().includes(this.searchQuery)
            );
        }

        // Update Nav counts
        const allCount = this.allSkills.length;
        const builtinCount = this.allSkills.filter(s => s.is_builtin).length;
        const externalCount = this.allSkills.filter(s => !s.is_builtin).length;
        const securityCount = this.allSkills.filter(s => s.risk !== 'low' || !s.is_builtin).length;

        document.getElementById('count-all').innerText = allCount;
        document.getElementById('count-builtin').innerText = builtinCount;
        document.getElementById('count-external').innerText = externalCount;
        document.getElementById('count-security').innerText = securityCount;

        if (filtered.length === 0) {
            this.grid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--text-secondary);">
                    <i class="fas fa-box-open" style="font-size: 32px; margin-bottom: 12px; display: block; opacity: 0.5;"></i>
                    <span>未找到匹配该过滤条件的技能组件</span>
                </div>
            `;
            return;
        }

        filtered.forEach(skill => {
            const card = document.createElement('div');
            card.className = 'skill-manager-card glass-surface';
            card.style.cssText = `
                padding: 16px;
                border-radius: 14px;
                border: 1px solid var(--border-color);
                display: flex;
                flex-direction: column;
                gap: 10px;
                cursor: pointer;
                position: relative;
                transition: transform 0.3s var(--apple-easing), box-shadow 0.3s var(--apple-easing);
            `;

            // Hover effect binding via events to respect style constraints
            card.onmouseenter = () => {
                card.style.transform = 'translateY(-4px)';
                card.style.boxShadow = '0 8px 24px rgba(0,0,0,0.15)';
            };
            card.onmouseleave = () => {
                card.style.transform = 'translateY(0)';
                card.style.boxShadow = 'none';
            };

            // Header Row with Icons and Badges
            const isBuiltinBadge = skill.is_builtin
                ? `<span style="font-size: 9px; background: rgba(0,122,255,0.15); color: #007AFF; padding: 2px 6px; border-radius: 6px; font-weight: 700;">内置</span>`
                : `<span style="font-size: 9px; background: rgba(255,149,0,0.15); color: #FF9500; padding: 2px 6px; border-radius: 6px; font-weight: 700;">外部扩展</span>`;

            const riskColors = {
                'low': { bg: 'rgba(52,199,89,0.15)', text: '#34C759', label: 'AST安全校验' },
                'medium': { bg: 'rgba(255,149,0,0.15)', text: '#FF9500', label: '进程隔离警告' },
                'high': { bg: 'rgba(255,59,48,0.15)', text: '#FF3B30', label: '沙箱隔离审计' }
            };
            const rStyle = riskColors[skill.risk] || riskColors['low'];
            const riskBadge = `<span style="font-size: 9px; background: ${rStyle.bg}; color: ${rStyle.text}; padding: 2px 6px; border-radius: 6px; font-weight: 700;">${rStyle.label}</span>`;

            const iconClass = skill.has_frontend ? 'fa-window-maximize' : 'fa-terminal';
            const iconColor = skill.is_builtin ? '#007AFF' : '#FF9500';

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <i class="fas ${iconClass}" style="color: ${iconColor}; font-size: 18px;"></i>
                        <span style="font-size: 14px; font-weight: 700; color: var(--text-primary);">${window.escapeHTML(skill.name)}</span>
                    </div>
                    <span style="font-size: 11px; font-family: monospace; color: var(--text-secondary); opacity: 0.8;">v${skill.version}</span>
                </div>
                <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.4; flex: 1;">
                    ${window.escapeHTML(skill.description)}
                </div>
                <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 5px;">
                    ${isBuiltinBadge}
                    ${riskBadge}
                    ${skill.has_frontend ? `<span style="font-size: 9px; background: rgba(52,199,89,0.15); color: #34C759; padding: 2px 6px; border-radius: 6px; font-weight: 700; text-transform: uppercase;">UI</span>` : ''}
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px; margin-top: 5px; font-size: 11px; color: var(--text-secondary);">
                    <span>作者: ${window.escapeHTML(skill.author)}</span>
                    <div style="display: flex; gap: 8px;">
                        ${!skill.is_builtin
                            ? `<button class="apple-btn-primary" onclick="skillsManager.uninstallSkill('${skill.id}', event)" style="background: rgba(255,59,48,0.1); color: #FF3B30; padding: 4px 8px; font-size: 11px; border-radius: 6px; border: none; cursor: pointer; display: flex; align-items: center; gap: 4px;"><i class="fas fa-trash-alt"></i> 卸载</button>`
                            : `<span style="font-size: 10px; opacity: 0.6;"><i class="fas fa-lock"></i> 系统核心保护</span>`
                        }
                    </div>
                </div>
            `;

            card.onclick = () => this.openSkill(skill);

            this.grid.appendChild(card);
        });
    }
}

window.toggleSkillsManager = () => {
    const el = document.getElementById('skills-manager-overlay');
    if (el) {
        el.classList.toggle('hidden');
        if (!el.classList.contains('hidden') && window.skillsManager) {
            window.skillsManager.init();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    window.skillsManager = new SkillsManagerController();
});
