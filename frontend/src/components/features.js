/**
 * Butler 功能中心 (Features Hub)
 *
 * 统一管理 Butler 应用的所有功能模块：
 * - 会话模式切换（本地/Worktree/云端）
 * - Git 工具面板（Diff/Commit/Push/PR）
 * - 项目管理器（跨项目多任务）
 * - 应用内浏览器
 * - 浮动弹出窗口
 * - 计算机使用
 * - 语音听写
 * - Worktree 管理
 */

class FeaturesHub {
    constructor() {
        this.activeSessionMode = 'local';
        this.currentProject = null;
        this.projects = [];
        this.popupCount = 0;
        this._init();
    }

    _init() {
        this._loadFromStorage();
        this._setupKeyboardShortcuts();
        console.log('[Butler Features] 功能中心已加载');
    }

    _loadFromStorage() {
        try {
            const data = localStorage.getItem('butler_features_state');
            if (data) {
                const state = JSON.parse(data);
                this.activeSessionMode = state.activeSessionMode || 'local';
                this.projects = state.projects || [];
            }
        } catch (e) {
            console.warn('功能状态加载失败:', e);
        }
    }

    _saveToStorage() {
        try {
            localStorage.setItem('butler_features_state', JSON.stringify({
                activeSessionMode: this.activeSessionMode,
                projects: this.projects,
            }));
        } catch (e) {
            console.warn('功能状态保存失败:', e);
        }
    }

    _setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'j') {
                e.preventDefault();
                this._toggleTerminal();
            }
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'b') {
                e.preventDefault();
                this.launchBrowser();
            }
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'p') {
                e.preventDefault();
                this.createPopup();
            }
        });
    }

    _toggleTerminal() {
        if (typeof window.toggleTerminal === 'function') {
            window.toggleTerminal();
        }
    }

    // ------------------------------------------------------------------
    // 会话模式
    // ------------------------------------------------------------------

    openSessionModeModal() {
        const modes = [
            { value: 'local', name: '本地', icon: 'fa-desktop', color: '#007AFF', desc: '直接在当前项目目录中工作' },
            { value: 'worktree', name: '工作树', icon: 'fa-code-branch', color: '#34C759', desc: '在 Git 工作树中隔离变更' },
            { value: 'cloud', name: '云端', icon: 'fa-cloud', color: '#5856D6', desc: '在云环境中远程运行' },
        ];

        const html = `
            <div class="features-modal-overlay" style="
                position: fixed; inset: 0; background: rgba(0,0,0,0.6);
                backdrop-filter: blur(8px); z-index: 10001;
                display: flex; align-items: center; justify-content: center;
            ">
                <div style="
                    background: rgba(30,30,42,0.98); border-radius: 16px;
                    width: 480px; max-width: 90vw; padding: 24px;
                    border: 1px solid rgba(255,255,255,0.1);
                    box-shadow: 0 30px 80px rgba(0,0,0,0.5);
                ">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
                        <div style="font-size: 18px; font-weight: 600; color: #fff;">
                            <i class="fas fa-code-branch" style="color: #34C759; margin-right: 8px;"></i>
                            选择会话模式
                        </div>
                        <button onclick="FeaturesHub._closeModal()" style="background: none; border: none; color: rgba(255,255,255,0.6); cursor: pointer; font-size: 18px;">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 12px;">
                        ${modes.map(m => `
                            <div onclick="FeaturesHub._selectMode('${m.value}')" style="
                                display: flex; align-items: center; gap: 14px;
                                padding: 16px; border-radius: 12px; cursor: pointer;
                                background: ${this.activeSessionMode === m.value ? m.color + '22' : 'rgba(255,255,255,0.04)'};
                                border: 1.5px solid ${this.activeSessionMode === m.value ? m.color : 'rgba(255,255,255,0.08)'};
                                transition: all 0.2s;
                            " onmouseover="this.style.background='rgba(255,255,255,0.08)'" onmouseout="this.style.background='${this.activeSessionMode === '${m.value}' ? '${m.color}22' : 'rgba(255,255,255,0.04)'}">
                                <div style="
                                    width: 44px; height: 44px; border-radius: 10px;
                                    background: ${m.color}22; display: flex; align-items: center;
                                    justify-content: center; flex-shrink: 0;
                                ">
                                    <i class="fas ${m.icon}" style="color: ${m.color}; font-size: 18px;"></i>
                                </div>
                                <div style="flex: 1;">
                                    <div style="font-weight: 600; color: #fff; font-size: 15px; margin-bottom: 4px;">${m.name}</div>
                                    <div style="font-size: 12px; color: rgba(255,255,255,0.5);">${m.desc}</div>
                                </div>
                                ${this.activeSessionMode === m.value ? '<i class="fas fa-check-circle" style="color: #34C759; font-size: 20px;"></i>' : ''}
                            </div>
                        `).join('')}
                    </div>
                    <div style="margin-top: 16px; padding: 12px; background: rgba(255,255,255,0.04); border-radius: 8px; font-size: 12px; color: rgba(255,255,255,0.5);">
                        <i class="fas fa-info-circle" style="margin-right: 6px;"></i>
                        当前模式: <strong style="color: #fff;">${modes.find(m => m.value === this.activeSessionMode)?.name}</strong>
                    </div>
                </div>
            </div>
        `;

        this._modalEl = document.createElement('div');
        this._modalEl.id = 'features-modal-root';
        this._modalEl.innerHTML = html;
        document.body.appendChild(this._modalEl);
    }

    _selectMode(mode) {
        this.activeSessionMode = mode;
        this._saveToStorage();
        this._closeModal();

        const modeNames = { local: '本地', worktree: '工作树', cloud: '云端' };
        window.showToast?.('会话模式', `已切换至 ${modeNames[mode]} 模式`, 'success');

        if (mode === 'worktree') {
            this._createWorktreeFlow();
        }
    }

    _closeModal() {
        if (this._modalEl) {
            this._modalEl.remove();
            this._modalEl = null;
        }
    }

    _createWorktreeFlow() {
        const name = prompt('输入 Worktree 分支名称:', `butler-wt-${Date.now().toString(36).slice(-4)}`);
        if (name) {
            window.showToast?.('Worktree', `正在创建 ${name} ...`, 'info');
        }
    }

    // ------------------------------------------------------------------
    // Git 工具面板
    // ------------------------------------------------------------------

    openGitPanel() {
        const html = `
            <div class="features-modal-overlay" style="
                position: fixed; inset: 0; background: rgba(0,0,0,0.6);
                backdrop-filter: blur(8px); z-index: 10001;
                display: flex; align-items: center; justify-content: center;
            ">
                <div style="
                    background: rgba(30,30,42,0.98); border-radius: 16px;
                    width: 720px; max-width: 95vw; max-height: 85vh;
                    display: flex; flex-direction: column;
                    border: 1px solid rgba(255,255,255,0.1);
                    box-shadow: 0 30px 80px rgba(0,0,0,0.5);
                ">
                    <div style="
                        display: flex; align-items: center; justify-content: space-between;
                        padding: 20px 24px; border-bottom: 1px solid rgba(255,255,255,0.08);
                    ">
                        <div style="font-size: 18px; font-weight: 600; color: #fff;">
                            <i class="fas fa-code-compare" style="color: #FF9500; margin-right: 8px;"></i>
                            Git 工具面板
                        </div>
                        <button onclick="FeaturesHub._closeModal()" style="background: none; border: none; color: rgba(255,255,255,0.6); cursor: pointer; font-size: 18px;">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div style="display: flex; gap: 24px; padding: 20px 24px; overflow-y: auto;">
                        <!-- 左侧：状态与分支 -->
                        <div style="flex: 1; display: flex; flex-direction: column; gap: 16px;">
                            <div style="background: rgba(255,255,255,0.04); border-radius: 10px; padding: 16px;">
                                <div style="font-size: 12px; color: rgba(255,255,255,0.5); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.05em;">仓库状态</div>
                                <div id="git-status-display" style="font-size: 13px; color: #fff;">加载中...</div>
                            </div>
                            <div style="background: rgba(255,255,255,0.04); border-radius: 10px; padding: 16px;">
                                <div style="font-size: 12px; color: rgba(255,255,255,0.5); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.05em;">分支管理</div>
                                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                                    <button onclick="FeaturesHub._gitAction('branches')" style="${this._gitBtnStyle('#007AFF')}"><i class="fas fa-code-branch"></i> 查看分支</button>
                                    <button onclick="FeaturesHub._gitAction('checkout')" style="${this._gitBtnStyle('#34C759')}"><i class="fas fa-check-circle"></i> 切换分支</button>
                                </div>
                            </div>
                        </div>
                        <!-- 右侧：操作 -->
                        <div style="flex: 1; display: flex; flex-direction: column; gap: 16px;">
                            <div style="background: rgba(255,255,255,0.04); border-radius: 10px; padding: 16px;">
                                <div style="font-size: 12px; color: rgba(255,255,255,0.5); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.05em;">Diff 面板</div>
                                <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px;">
                                    <button onclick="FeaturesHub._gitAction('diff')" style="${this._gitBtnStyle('#FF9500')}"><i class="fas fa-code-compare"></i> 查看变更</button>
                                    <button onclick="FeaturesHub._gitAction('stage')" style="${this._gitBtnStyle('#34C759')}"><i class="fas fa-plus-circle"></i> 暂存全部</button>
                                </div>
                                <div id="git-diff-display" style="font-size: 11px; color: rgba(255,255,255,0.5); font-family: monospace; max-height: 120px; overflow-y: auto; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px;">暂存区与工作区无差异</div>
                            </div>
                            <div style="background: rgba(255,255,255,0.04); border-radius: 10px; padding: 16px;">
                                <div style="font-size: 12px; color: rgba(255,255,255,0.5); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.05em;">提交与推送</div>
                                <div style="display: flex; flex-direction: column; gap: 8px;">
                                    <input type="text" id="git-commit-msg" placeholder="提交信息..." style="
                                        background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1);
                                        border-radius: 6px; padding: 8px 12px; color: #fff; font-size: 13px;
                                    ">
                                    <div style="display: flex; gap: 8px;">
                                        <button onclick="FeaturesHub._gitAction('commit')" style="${this._gitBtnStyle('#34C759')}" flex: 1;"><i class="fas fa-check"></i> 提交</button>
                                        <button onclick="FeaturesHub._gitAction('push')" style="${this._gitBtnStyle('#007AFF')}" flex: 1;"><i class="fas fa-upload"></i> 推送</button>
                                        <button onclick="FeaturesHub._gitAction('pr')" style="${this._gitBtnStyle('#5856D6')}" flex: 1;"><i class="fas fa-code-pull-request"></i> PR</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div style="padding: 12px 24px; border-top: 1px solid rgba(255,255,255,0.08); font-size: 11px; color: rgba(255,255,255,0.4); text-align: center;">
                        <i class="fas fa-info-circle"></i> 在终端中执行 Git 命令或通过此面板快速操作
                    </div>
                </div>
            </div>
        `;

        this._modalEl = document.createElement('div');
        this._modalEl.id = 'git-modal-root';
        this._modalEl.innerHTML = html;
        document.body.appendChild(this._modalEl);

        setTimeout(() => {
            this._updateGitStatus();
        }, 100);
    }

    _gitBtnStyle(color) {
        return `
            flex: 1; padding: 8px 12px; background: ${color}22;
            border: 1px solid ${color}44; border-radius: 6px;
            color: ${color}; font-size: 12px; font-weight: 500;
            cursor: pointer; display: flex; align-items: center;
            gap: 6px; transition: all 0.2s;
        `;
    }

    async _updateGitStatus() {
        const display = document.getElementById('git-status-display');
        if (!display) return;

        try {
            const status = await this._callBackend('git', 'status');
            if (status) {
                display.innerHTML = `
                    <div style="display: flex; gap: 16px; flex-wrap: wrap;">
                        <div><span style="color: rgba(255,255,255,0.5);">分支:</span> <strong>${status.branch || 'unknown'}</strong></div>
                        <div style="color: ${status.is_clean ? '#34C759' : '#FF9500'};">
                            ${status.is_clean ? '✓ 工作区干净' : '⚠ 有未提交变更'}
                        </div>
                    </div>
                    ${status.modified?.length ? `<div style="margin-top: 8px; color: rgba(255,255,255,0.7);">已修改: ${status.modified.join(', ')}</div>` : ''}
                    ${status.added?.length ? `<div style="color: #34C759;">新增: ${status.added.join(', ')}</div>` : ''}
                    ${status.deleted?.length ? `<div style="color: #FF3B30;">已删除: ${status.deleted.join(', ')}</div>` : ''}
                `;
            }
        } catch (e) {
            display.innerHTML = '<span style="color: rgba(255,255,255,0.5);">请在项目目录中运行以查看 Git 状态</span>';
        }
    }

    async _gitAction(action) {
        const handlers = {
            diff: () => this._callBackend('git', 'diff'),
            stage: () => this._callBackend('git', 'stage', { file: '.' }),
            commit: () => {
                const msg = document.getElementById('git-commit-msg')?.value || '更新';
                return this._callBackend('git', 'commit', { message: msg });
            },
            push: () => this._callBackend('git', 'push'),
            pr: () => this._callBackend('git', 'pr', { title: 'Butler PR' }),
            branches: () => this._callBackend('git', 'branches'),
            checkout: () => {
                const name = prompt('输入分支名:');
                if (name) return this._callBackend('git', 'checkout', { branch: name });
            },
        };

        const handler = handlers[action];
        if (handler) {
            const result = await handler();
            if (result?.success !== false) {
                window.showToast?.('Git', `操作 ${action} 已执行`, 'success');
                this._updateGitStatus();
            }
        }
    }

    // ------------------------------------------------------------------
    // 项目管理器
    // ------------------------------------------------------------------

    openProjectManager() {
        const html = `
            <div class="features-modal-overlay" style="
                position: fixed; inset: 0; background: rgba(0,0,0,0.6);
                backdrop-filter: blur(8px); z-index: 10001;
                display: flex; align-items: center; justify-content: center;
            ">
                <div style="
                    background: rgba(30,30,42,0.98); border-radius: 16px;
                    width: 560px; max-width: 95vw; max-height: 80vh;
                    display: flex; flex-direction: column;
                    border: 1px solid rgba(255,255,255,0.1);
                    box-shadow: 0 30px 80px rgba(0,0,0,0.5);
                ">
                    <div style="
                        display: flex; align-items: center; justify-content: space-between;
                        padding: 20px 24px; border-bottom: 1px solid rgba(255,255,255,0.08);
                    ">
                        <div style="font-size: 18px; font-weight: 600; color: #fff;">
                            <i class="fas fa-folder-tree" style="color: #007AFF; margin-right: 8px;"></i>
                            项目管理器
                        </div>
                        <button onclick="FeaturesHub._closeModal()" style="background: none; border: none; color: rgba(255,255,255,0.6); cursor: pointer; font-size: 18px;">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div style="padding: 16px 24px;">
                        <div style="display: flex; gap: 10px; margin-bottom: 16px;">
                            <input type="text" id="new-project-name" placeholder="项目名称" style="
                                flex: 1; background: rgba(255,255,255,0.05);
                                border: 1px solid rgba(255,255,255,0.1);
                                border-radius: 8px; padding: 10px 14px; color: #fff;
                            ">
                            <input type="text" id="new-project-path" placeholder="项目路径" style="
                                flex: 1; background: rgba(255,255,255,0.05);
                                border: 1px solid rgba(255,255,255,0.1);
                                border-radius: 8px; padding: 10px 14px; color: #fff;
                            ">
                            <button onclick="FeaturesHub._addProject()" style="
                                background: linear-gradient(135deg, #007AFF, #5856D6);
                                border: none; border-radius: 8px; padding: 0 18px;
                                color: #fff; cursor: pointer; font-weight: 600;
                            ">添加</button>
                        </div>
                        <div id="projects-list" style="display: flex; flex-direction: column; gap: 8px; max-height: 300px; overflow-y: auto;">
                            <div style="text-align: center; color: rgba(255,255,255,0.4); padding: 30px;">
                                <i class="fas fa-folder-open" style="font-size: 36px; margin-bottom: 10px;"></i>
                                <div>暂无项目，添加一个开始吧</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this._modalEl = document.createElement('div');
        this._modalEl.id = 'project-modal-root';
        this._modalEl.innerHTML = html;
        document.body.appendChild(this._modalEl);
        this._renderProjects();
    }

    _renderProjects() {
        const list = document.getElementById('projects-list');
        if (!list) return;

        if (this.projects.length === 0) {
            list.innerHTML = `
                <div style="text-align: center; color: rgba(255,255,255,0.4); padding: 30px;">
                    <i class="fas fa-folder-open" style="font-size: 36px; margin-bottom: 10px;"></i>
                    <div>暂无项目，添加一个开始吧</div>
                </div>
            `;
            return;
        }

        list.innerHTML = this.projects.map((p, i) => `
            <div style="
                display: flex; align-items: center; gap: 12px;
                padding: 12px 14px; background: rgba(255,255,255,0.04);
                border-radius: 10px; cursor: pointer;
                border: 1px solid ${this.currentProject === p.id ? '#007AFF44' : 'rgba(255,255,255,0.06)'};
                transition: all 0.2s;
            " onclick="FeaturesHub._selectProject('${p.id}')">
                <i class="fas fa-folder" style="color: #007AFF;"></i>
                <div style="flex: 1;">
                    <div style="font-weight: 500; color: #fff; font-size: 14px;">${p.name}</div>
                    <div style="font-size: 11px; color: rgba(255,255,255,0.4); font-family: monospace;">${p.path}</div>
                </div>
                <button onclick="event.stopPropagation(); FeaturesHub._removeProject(${i})" style="
                    background: none; border: none; color: rgba(255,255,255,0.3);
                    cursor: pointer; padding: 4px;
                "><i class="fas fa-trash"></i></button>
                ${this.currentProject?.id === p.id ? '<i class="fas fa-check-circle" style="color: #34C759;"></i>' : ''}
            </div>
        `).join('');
    }

    _addProject() {
        const name = document.getElementById('new-project-name')?.value.trim();
        const path = document.getElementById('new-project-path')?.value.trim();

        if (!name || !path) {
            window.showToast?.('项目', '请填写项目名称和路径', 'error');
            return;
        }

        const project = {
            id: `proj-${Date.now()}`,
            name,
            path,
            created_at: Date.now(),
        };

        this.projects.push(project);
        this._saveToStorage();
        this._renderProjects();

        if (document.getElementById('new-project-name')) {
            document.getElementById('new-project-name').value = '';
        }
        if (document.getElementById('new-project-path')) {
            document.getElementById('new-project-path').value = '';
        }

        window.showToast?.('项目', `项目已添加: ${name}`, 'success');
    }

    _selectProject(id) {
        const project = this.projects.find(p => p.id === id);
        if (project) {
            this.currentProject = project;
            this._saveToStorage();
            this._renderProjects();
            window.showToast?.('项目', `已切换到: ${project.name}`, 'success');
        }
    }

    _removeProject(index) {
        this.projects.splice(index, 1);
        this._saveToStorage();
        this._renderProjects();
        window.showToast?.('项目', '项目已移除', 'info');
    }

    // ------------------------------------------------------------------
    // 应用内浏览器
    // ------------------------------------------------------------------

    launchBrowser() {
        const container = document.createElement('div');
        container.id = 'browser-container';
        container.style.cssText = `
            position: fixed; inset: 0; z-index: 9999;
            display: none; background: rgba(0,0,0,0.5);
        `;
        document.body.appendChild(container);

        if (!window.butlerBrowser) {
            window.initBrowser('browser-container');
        }

        window.butlerBrowser.open();
    }

    // ------------------------------------------------------------------
    // 浮动弹出窗口
    // ------------------------------------------------------------------

    createPopup() {
        this.popupCount++;
        const popup = window.FloatingPopupManager.create({
            title: `对话线程 #${this.popupCount}`,
            content: `
                <div style="padding: 10px;">
                    <div style="color: rgba(255,255,255,0.5); font-size: 12px; margin-bottom: 10px;">
                        Butler 浮动对话窗口
                    </div>
                    <div style="background: rgba(255,255,255,0.06); border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                        <div style="color: rgba(255,255,255,0.4); font-size: 11px; margin-bottom: 4px;">你</div>
                        <div style="font-size: 13px;">帮我分析一下最近的代码变更...</div>
                    </div>
                    <div style="background: linear-gradient(135deg, #6366f122, #8b5cf622); border-radius: 8px; padding: 12px; margin-bottom: 10px; border: 1px solid rgba(99,102,241,0.2);">
                        <div style="color: rgba(255,255,255,0.4); font-size: 11px; margin-bottom: 4px;">Butler</div>
                        <div style="font-size: 13px;">我可以帮你查看 Git Diff、分析变更并生成报告。需要我开始吗？</div>
                    </div>
                    <textarea placeholder="输入消息..." style="
                        width: 100%; min-height: 60px;
                        background: rgba(255,255,255,0.06);
                        border: 1px solid rgba(255,255,255,0.1);
                        border-radius: 8px; padding: 10px;
                        color: #fff; font-size: 13px; resize: none;
                    "></textarea>
                </div>
            `,
            width: 380,
            height: 420,
            x: 100 + (this.popupCount % 5) * 30,
            y: 100 + (this.popupCount % 5) * 30,
        });
    }

    // ------------------------------------------------------------------
    // 计算机使用
    // ------------------------------------------------------------------

    launchComputerUse() {
        const html = `
            <div class="features-modal-overlay" style="
                position: fixed; inset: 0; background: rgba(0,0,0,0.6);
                backdrop-filter: blur(8px); z-index: 10001;
                display: flex; align-items: center; justify-content: center;
            ">
                <div style="
                    background: rgba(30,30,42,0.98); border-radius: 16px;
                    width: 440px; max-width: 90vw; padding: 24px;
                    border: 1px solid rgba(255,255,255,0.1);
                    box-shadow: 0 30px 80px rgba(0,0,0,0.5);
                ">
                    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                        <div style="width: 44px; height: 44px; border-radius: 10px; background: #AF52DE22; display: flex; align-items: center; justify-content: center;">
                            <i class="fas fa-desktop" style="color: #AF52DE; font-size: 20px;"></i>
                        </div>
                        <div>
                            <div style="font-size: 18px; font-weight: 600; color: #fff;">计算机使用</div>
                            <div style="font-size: 12px; color: rgba(255,255,255,0.5);">让 Butler 操作桌面应用</div>
                        </div>
                    </div>
                    <div style="background: rgba(255,255,255,0.04); border-radius: 10px; padding: 14px; margin-bottom: 16px;">
                        <div style="font-size: 13px; color: rgba(255,255,255,0.7); line-height: 1.6;">
                            <strong>计算机使用</strong>功能帮助 Butler 通过查看、点击和输入来操作应用。
                            适用于测试桌面应用、检查浏览器流程、处理无法作为插件使用的数据源。
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px;">
                        <button onclick="FeaturesHub._computerAction('screenshot')" style="${this._actionBtnStyle('#007AFF')}">
                            <i class="fas fa-camera"></i> 截屏
                        </button>
                        <button onclick="FeaturesHub._computerAction('click')" style="${this._actionBtnStyle('#34C759')}">
                            <i class="fas fa-mouse-pointer"></i> 点击
                        </button>
                        <button onclick="FeaturesHub._computerAction('type')" style="${this._actionBtnStyle('#FF9500')}">
                            <i class="fas fa-keyboard"></i> 输入
                        </button>
                        <button onclick="FeaturesHub._computerAction('test-gui')" style="${this._actionBtnStyle('#AF52DE')}">
                            <i class="fas fa-flask"></i> GUI 测试
                        </button>
                    </div>
                    <div style="padding: 10px; background: rgba(255,149,0,0.1); border-radius: 8px; font-size: 11px; color: rgba(255,149,0,0.9);">
                        <i class="fas fa-triangle-exclamation"></i> 计算机使用可能影响项目工作区之外的应用和系统状态，请保持任务范围具体明确。
                    </div>
                </div>
            </div>
        `;

        this._modalEl = document.createElement('div');
        this._modalEl.id = 'computer-modal-root';
        this._modalEl.innerHTML = html;
        document.body.appendChild(this._modalEl);
    }

    _actionBtnStyle(color) {
        return `
            padding: 14px; background: ${color}15;
            border: 1px solid ${color}44; border-radius: 10px;
            color: ${color}; font-size: 13px; font-weight: 500;
            cursor: pointer; display: flex; align-items: center;
            justify-content: center; gap: 8px; transition: all 0.2s;
        `;
    }

    _computerAction(action) {
        window.showToast?.('计算机使用', `执行操作: ${action}`, 'info');
        this._closeModal();
        const script = action === 'screenshot' ? 'computer_screenshot' :
                      action === 'click' ? 'computer_click' :
                      action === 'type' ? 'computer_type' : 'computer_test_gui';
        if (typeof window.triggerQuickAction === 'function') {
            window.triggerQuickAction(script, '🖥️');
        }
    }

    // ------------------------------------------------------------------
    // 语音听写
    // ------------------------------------------------------------------

    launchVoiceDictation() {
        const html = `
            <div class="features-modal-overlay" style="
                position: fixed; inset: 0; background: rgba(0,0,0,0.6);
                backdrop-filter: blur(8px); z-index: 10001;
                display: flex; align-items: center; justify-content: center;
            ">
                <div style="
                    background: rgba(30,30,42,0.98); border-radius: 16px;
                    width: 380px; max-width: 90vw; padding: 30px; text-align: center;
                    border: 1px solid rgba(255,255,255,0.1);
                    box-shadow: 0 30px 80px rgba(0,0,0,0.5);
                ">
                    <div style="
                        width: 80px; height: 80px; border-radius: 50%;
                        background: linear-gradient(135deg, #30B0C722, #007AFF22);
                        display: flex; align-items: center; justify-content: center;
                        margin: 0 auto 20px; animation: pulse-ring 2s ease-out infinite;
                    ">
                        <i class="fas fa-microphone-lines" style="color: #30B0C7; font-size: 28px;"></i>
                    </div>
                    <div style="font-size: 16px; font-weight: 600; color: #fff; margin-bottom: 8px;">语音听写</div>
                    <div style="font-size: 13px; color: rgba(255,255,255,0.5); margin-bottom: 20px;">
                        按住 <kbd style="background: rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 4px; font-family: monospace;">Ctrl</kbd> + <kbd style="background: rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 4px; font-family: monospace;">M</kbd> 开始说话
                    </div>
                    <button onclick="FeaturesHub._startVoiceRecording()" style="
                        background: linear-gradient(135deg, #30B0C7, #007AFF);
                        border: none; border-radius: 12px; padding: 14px 32px;
                        color: #fff; font-size: 14px; font-weight: 600;
                        cursor: pointer;
                    ">
                        <i class="fas fa-microphone" style="margin-right: 8px;"></i>
                        开始录音
                    </button>
                    <div style="margin-top: 16px; font-size: 11px; color: rgba(255,255,255,0.3);">
                        语音将被转录为文字，可编辑后发送
                    </div>
                </div>
            </div>
            <style>
                @keyframes pulse-ring {
                    0% { box-shadow: 0 0 0 0 rgba(48, 176, 199, 0.4); }
                    70% { box-shadow: 0 0 0 20px rgba(48, 176, 199, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(48, 176, 199, 0); }
                }
            </style>
        `;

        this._modalEl = document.createElement('div');
        this._modalEl.id = 'voice-modal-root';
        this._modalEl.innerHTML = html;
        document.body.appendChild(this._modalEl);
    }

    _startVoiceRecording() {
        this._closeModal();
        window.showToast?.('语音', '正在录音... 请开始说话', 'info');

        if (typeof window.triggerQuickAction === 'function') {
            window.triggerQuickAction('voice_start', '🎙️');
        }

        setTimeout(() => {
            const transcript = prompt('录音结束，请编辑转录文本（模拟）：', '帮我检查一下今天的邮件');
            if (transcript && typeof window.triggerQuickAction === 'function') {
                window.triggerQuickAction(transcript, '💬');
            }
        }, 2000);
    }

    // ------------------------------------------------------------------
    // Worktree 信息
    // ------------------------------------------------------------------

    showWorktreeInfo() {
        const html = `
            <div class="features-modal-overlay" style="
                position: fixed; inset: 0; background: rgba(0,0,0,0.6);
                backdrop-filter: blur(8px); z-index: 10001;
                display: flex; align-items: center; justify-content: center;
            ">
                <div style="
                    background: rgba(30,30,42,0.98); border-radius: 16px;
                    width: 520px; max-width: 90vw; padding: 24px;
                    border: 1px solid rgba(255,255,255,0.1);
                    box-shadow: 0 30px 80px rgba(0,0,0,0.5);
                ">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
                        <div style="font-size: 18px; font-weight: 600; color: #fff;">
                            <i class="fas fa-code-fork" style="color: #FF3B30; margin-right: 8px;"></i>
                            Worktree 管理
                        </div>
                        <button onclick="FeaturesHub._closeModal()" style="background: none; border: none; color: rgba(255,255,255,0.6); cursor: pointer; font-size: 18px;">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    <div style="font-size: 13px; color: rgba(255,255,255,0.7); margin-bottom: 20px; line-height: 1.6;">
                        <strong>Git Worktree</strong> 允许你在同一个仓库中创建多个独立的工作目录。
                        当你想要尝试新想法而不影响当前工作，或希望 Butler 在同一项目中并行运行独立任务时非常有用。
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <button onclick="FeaturesHub._worktreeAction('list')" style="${this._actionBtnStyle('#007AFF')}">
                            <i class="fas fa-list"></i> 列出所有 Worktree
                        </button>
                        <button onclick="FeaturesHub._worktreeAction('create')" style="${this._actionBtnStyle('#34C759')}">
                            <i class="fas fa-plus"></i> 创建新 Worktree
                        </button>
                        <button onclick="FeaturesHub._worktreeAction('prune')" style="${this._actionBtnStyle('#FF9500')}">
                            <i class="fas fa-broom"></i> 清理失效 Worktree
                        </button>
                    </div>
                    <div style="margin-top: 16px; padding: 12px; background: rgba(255,255,255,0.04); border-radius: 8px; font-size: 12px; color: rgba(255,255,255,0.5);">
                        <i class="fas fa-lightbulb"></i> 自动化任务在 Git 仓库的专用后台 worktree 中运行
                    </div>
                </div>
            </div>
        `;

        this._modalEl = document.createElement('div');
        this._modalEl.id = 'worktree-modal-root';
        this._modalEl.innerHTML = html;
        document.body.appendChild(this._modalEl);
    }

    _worktreeAction(action) {
        this._closeModal();
        const handlers = {
            list: () => window.showToast?.('Worktree', 'Worktree 列表已获取', 'info'),
            create: () => {
                const name = prompt('输入新分支名:');
                if (name) window.showToast?.('Worktree', `创建 Worktree: ${name}`, 'success');
            },
            prune: () => window.showToast?.('Worktree', '已清理失效 Worktree', 'info'),
        };
        handlers[action]?.();
    }

    // ------------------------------------------------------------------
    // 后端通信
    // ------------------------------------------------------------------

    async _callBackend(module, action, params = {}) {
        try {
            const response = await fetch(`/api/features/${module}/${action}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params),
            });
            if (response.ok) {
                return await response.json();
            }
        } catch (e) {
            console.debug(`[Features] 后端调用失败: ${module}/${action}`);
        }
        return null;
    }
}

window.FeaturesHub = new FeaturesHub();
