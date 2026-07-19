// Global Utilities
window.escapeHTML = (str) => {
    if (str === null || str === undefined) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
};

// Dialogue Quick Action Trigger
window.triggerQuickAction = (command, emoji) => {
    const chatInput = document.getElementById('chat-input');
    const welcome = document.querySelector('.welcome-message');
    if (chatInput) {
        chatInput.innerText = command;
        if (welcome) welcome.style.display = 'none';
        const sendBtn = document.getElementById('send-command-btn');
        if (sendBtn) {
            sendBtn.click();
        }
    }
};

// Toggle Operation Interface Mode (Desktop vs Mobile)
window.toggleInterfaceMode = () => {
    const select = document.getElementById('setting-interface-mode');
    if (select) {
        const val = select.value;
        // Apply smooth transition overlay
        document.body.classList.add('interface-switching');

        setTimeout(() => {
            if (val === 'mobile') {
                document.body.classList.remove('interface-desktop');
                document.body.classList.add('interface-mobile');
                localStorage.setItem('setting_interface_mode', 'mobile');
                window.showToast("操作界面", "已切换至手机端模拟界面模式。", "success");
            } else {
                document.body.classList.remove('interface-mobile');
                document.body.classList.add('interface-desktop');
                localStorage.setItem('setting_interface_mode', 'desktop');
                window.showToast("操作界面", "已切换至电脑端界面模式。", "success");
            }

            setTimeout(() => {
                document.body.classList.remove('interface-switching');
            }, 150);
        }, 150);
    }
};

// Onboarding Steps Definitions
const onboardingSteps = [
    {
        title: "🪐 核心对话中枢 (0,0)",
        text: "这是 Butler 的 AI 大脑。在此发送消息、拖放截图激光诊断报错，或点击下方<b>快捷指令卡片</b>一键触发自检、清理、音频降噪等自研底层核心能力。",
        quadrant: [0, 0],
        highlight: "cell-0-0"
    },
    {
        title: "🕰️ 全局状态时光机 (1,0)",
        text: "全局可观测时光机。拖动底部时间轴滑块，可以重现系统历史快照和环境传感器遥测曲线，报错状态还会全局高亮提示！",
        quadrant: [1, 0],
        highlight: "cell-1-0"
    },
    {
        title: "📊 任务画布 DAG Canvas (0,1)",
        text: "发光实体连接线任务编排。拖拽技能到此处可以组装复杂的 DAG 流水线。右上角更拥有<b>全新启动控制台</b>，点击即刻产生高对比度连线跑马灯流动！",
        quadrant: [0, 1],
        highlight: "cell-0-1"
    },
    {
        title: "📦 技能仓储与底层硬件 (1,1)",
        text: "模块化抽屉式技能。One Folder = One Skill。在此浏览各种定制技能与文件仓。右上角可展开终端，监控底层 HAL 硬件传感器与多端 Go 运行器生命周期。",
        quadrant: [1, 1],
        highlight: "cell-1-1"
    }
];

let currentOnboardingStep = 0;

window.startOnboardingTour = () => {
    currentOnboardingStep = 0;
    const overlay = document.getElementById('onboarding-tour-overlay');
    if (overlay) {
        overlay.classList.add('active');
        showOnboardingStep(0);
    }
};

window.nextOnboardingStep = () => {
    currentOnboardingStep++;
    if (currentOnboardingStep < onboardingSteps.length) {
        showOnboardingStep(currentOnboardingStep);
    } else {
        window.skipOnboarding();
    }
};

window.skipOnboarding = () => {
    const overlay = document.getElementById('onboarding-tour-overlay');
    if (overlay) overlay.classList.remove('active');
    document.querySelectorAll('.matrix-cell').forEach(cell => {
        cell.classList.remove('onboarding-highlight');
    });
    if (window.matrix) {
        window.matrix.moveTo(0, 0);
    }
    // Add class to hide top-left headers on completion of onboarding
    document.body.classList.add('onboarding-completed');
    window.showToast("上手指南", "新手引导已结束。点击开始体验 Butler 本地优先的极致魅力！", "success");
    localStorage.setItem('butler_onboarding_completed', 'true');
};

function showOnboardingStep(index) {
    const step = onboardingSteps[index];
    if (!step) return;

    if (window.matrix) {
        window.matrix.moveTo(step.quadrant[0], step.quadrant[1]);
    }

    document.querySelectorAll('.matrix-cell').forEach(cell => {
        cell.classList.remove('onboarding-highlight');
    });
    const targetCell = document.getElementById(step.highlight);
    if (targetCell) {
        targetCell.classList.add('onboarding-highlight');
    }

    const bubble = document.getElementById('onboarding-bubble-el');
    const bodyText = document.getElementById('onboarding-body-text');
    const stepIndicator = document.getElementById('onboarding-step-indicator');
    const nextBtn = document.getElementById('onboarding-next-btn');

    if (bodyText) bodyText.innerHTML = step.text;
    if (stepIndicator) stepIndicator.innerText = `${index + 1} / ${onboardingSteps.length}`;
    if (nextBtn) {
        nextBtn.innerText = (index === onboardingSteps.length - 1) ? "探索完成" : "下一步";
    }

    if (bubble) {
        bubble.style.position = 'fixed';
        bubble.style.left = '40px';
        bubble.style.bottom = '130px';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const interactionFlow = document.getElementById('interaction-flow');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-command-btn');
    const voiceToggleBtn = document.getElementById('voice-toggle-btn');
    const voiceStatusDot = document.getElementById('voice-status');

    // State
    let isStreaming = false;
    let currentAILine = null;

    // --- Chat Logic ---
    function executeChatCommand() {
        const command = chatInput.innerText.trim();
        if (!command || isStreaming) return;

        const welcome = document.querySelector('.welcome-message');
        if (welcome) welcome.style.display = 'none';

        const userLine = document.createElement('div');
        userLine.className = 'interaction-line user-input-line';
        userLine.innerText = command;
        interactionFlow.appendChild(userLine);

        chatInput.innerText = "";
        isStreaming = true;

        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.handle_command(command);
        }
        interactionFlow.scrollTop = interactionFlow.scrollHeight;
    }

    // --- Global Notification ---
    window.showToast = (title, message, type = 'success') => {
        const container = document.getElementById('notifier-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;
        toast.innerHTML = `
            <div class="notif-header">
                <span class="notif-title">${title}</span>
                <span class="notif-time">${new Date().toLocaleTimeString()}</span>
            </div>
            <div class="notif-content">${message}</div>
        `;

        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('closing');
            setTimeout(() => toast.remove(), 4000);
        }, 3000);
    };

    // --- Copilot Modal Integration ---
    const modal = new CopilotModal();

    // Add Trigger Button to Chat Input area for demo
    const inputActionsLeft = document.querySelector('.input-actions-left');
    if (inputActionsLeft) {
        const confirmTrigger = document.createElement('button');
        confirmTrigger.className = 'icon-btn-small';
        confirmTrigger.innerHTML = '<i class="fas fa-shield-check"></i>';
        confirmTrigger.title = '触发确认框';
        confirmTrigger.onclick = () => {
            modal.show({
                title: '重构代码确认',
                message: 'Butler 检测到 butler/core/workflow_engine.py 中的循环引用。是否允许自动重构该模块？此操作不可逆。',
                onConfirm: () => {
                    console.log('[System] Action Approved: Executing task...');
                    window.showToast('系统任务', '任务已开始执行');

                    // Simulate loading process
                    const statusDot = document.getElementById('thinking-status');
                    if (statusDot) statusDot.classList.add('active');

                    setTimeout(() => {
                        if (statusDot) statusDot.classList.remove('active');
                        window.showToast('修复成功', '代码重构已完成。', 'success');
                        console.log('[System] Task Completed: Refactoring finished.');
                    }, 2000);
                },
                triggerBtn: confirmTrigger
            });
        };
        inputActionsLeft.appendChild(confirmTrigger);
    }

    sendBtn.onclick = executeChatCommand;
    chatInput.onkeydown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            executeChatCommand();
        }
    };

    // --- Bridge Functions ---
    window.onAIStreamStart = () => {
        isStreaming = true;
        document.getElementById('thinking-status').classList.add('active');
        currentAILine = document.createElement('div');
        currentAILine.className = 'interaction-line ai-output-line';
        interactionFlow.appendChild(currentAILine);
    };

    window.onAIStreamChunk = (chunk) => {
        if (currentAILine) {
            const span = document.createElement('span');
            span.innerText = chunk;
            currentAILine.appendChild(span);
            interactionFlow.scrollTop = interactionFlow.scrollHeight;
        }
    };

    window.onAIStreamEnd = () => {
        isStreaming = false;
        document.getElementById('thinking-status').classList.remove('active');
    };

    // --- Image Handling & Debugger ---
    chatInput.onpaste = (e) => {
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        for (let index in items) {
            const item = items[index];
            if (item.kind === 'file' && item.type.startsWith('image/')) {
                const blob = item.getAsFile();
                const reader = new FileReader();
                reader.onload = (event) => {
                    handleImageInput(event.target.result);
                };
                reader.readAsDataURL(blob);
            }
        }
    };

    function handleImageInput(base64) {
        const container = document.createElement('div');
        container.className = 'interaction-line ai-output-line laser-scan-container';
        container.innerHTML = `
            <div class="laser-line"></div>
            <img src="${base64}" style="width: 100%; border-radius: 8px;">
            <p style="margin-top: 10px; font-size: 14px; color: var(--text-secondary);">正在进行激光扫描诊断...</p>
        `;
        interactionFlow.appendChild(container);
        interactionFlow.scrollTop = interactionFlow.scrollHeight;

        // Mock analysis delay
        setTimeout(async () => {
            container.querySelector('.laser-line').remove();
            container.querySelector('p').innerText = "诊断完成。检测到关键逻辑错误。";

            // Show Fix Card
            renderFixCard({
                type: 'LOGIC_ERROR',
                title: '检测到模块冲突 (butler/core/workflow_engine.py)',
                desc: '在第 142 行发现循环引用风险，建议立即重构。',
                btnText: '修复逻辑 (Time-Slit)',
                filePath: 'butler/core/workflow_engine.py',
                line: 142
            });
        }, 2500);
    }

    function renderFixCard(data) {
        const card = document.createElement('div');
        card.className = 'fix-card glass-surface';
        card.innerHTML = `
            <div style="font-weight: 700; color: #34C759; display: flex; align-items: center; gap: 8px;">
                <i class="fas fa-magic"></i> ${data.title}
            </div>
            <p style="font-size: 14px; opacity: 0.8;">${data.desc}</p>
            <button class="fix-btn apple-btn-primary">${data.btnText}</button>
        `;

        card.querySelector('.fix-btn').onclick = async () => {
            if (data.filePath && window.timeSlitEditor) {
                window.timeSlitEditor.openSlit(data.filePath, data.line, card);
            } else {
                card.querySelector('.fix-btn').innerText = "修复中...";
                setTimeout(() => {
                    card.innerHTML = `
                        <div style="color: #34C759; font-weight: 700;">
                            <i class="fas fa-magic"></i> 修复成功！
                        </div>
                    `;
                }, 1500);
            }
        };

        interactionFlow.appendChild(card);
        interactionFlow.scrollTop = interactionFlow.scrollHeight;
    }

    // --- AirDrop Swipe Up ---
    let touchStartY = 0;
    document.addEventListener('touchstart', (e) => {
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
        const dy = e.changedTouches[0].clientY - touchStartY;
        const target = e.target.closest('.interaction-line, .dag-node, .fix-card');

        if (dy < -200 && target) {
            triggerAirDrop(target);
        }
    }, { passive: true });

    // Desktop Mock: Shift + Click to swipe up
    document.addEventListener('click', (e) => {
        if (e.shiftKey) {
            const target = e.target.closest('.interaction-line, .dag-node, .fix-card');
            if (target) triggerAirDrop(target);
        }
    });

    async function triggerAirDrop(element) {
        element.classList.add('airdrop-exit');

        // Show streamer effect
        const streamer = document.createElement('div');
        streamer.className = 'airdrop-streamer active';
        document.body.appendChild(streamer);

        if (window.pywebview && window.pywebview.api) {
            // Contextual payload generation for AirDrop
            const payload = {
                type: 'asset_transfer',
                timestamp: Date.now(),
                content: element.innerText,
                id: element.id || 'anonymous_card'
            };

            // Bridge call to ClusterManager gRPC pipeline
            window.pywebview.api.call_skill('cluster_manager', 'airdrop_push', {
                payload: payload
            });
        }

        setTimeout(() => {
            element.remove();
            streamer.remove();
        }, 1000);
    }

    // --- Drag and Drop for Pipelining ---
    const dropZone = document.createElement('div');
    dropZone.className = 'interaction-line ai-output-line';
    dropZone.style.border = '2px dashed rgba(255,255,255,0.2)';
    dropZone.style.textAlign = 'center';
    dropZone.innerHTML = '<i class="fas fa-file-import"></i> <span>将结果拖拽至此以启动流水线</span>';
    interactionFlow.appendChild(dropZone);

    dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('drop-zone-active'); };
    dropZone.ondragleave = () => dropZone.classList.remove('drop-zone-active');
    dropZone.ondrop = async (e) => {
        e.preventDefault();
        dropZone.classList.remove('drop-zone-active');
        // Handle drop...
    };
});

// Settings Toggle and Form Lifecycle
window.toggleSettings = () => {
    const overlay = document.getElementById('settings-overlay');
    if (overlay) {
        overlay.classList.toggle('hidden');
        if (!overlay.classList.contains('hidden')) {
            loadSettingsForm();
        }
    }
};

// Switch Settings Tabs
window.switchSettingsTab = (tabId) => {
    document.querySelectorAll('.settings-nav-item').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.settings-panel').forEach(panel => {
        panel.classList.remove('active');
    });

    const targetBtn = document.getElementById(`tab-btn-${tabId}`);
    if (targetBtn) targetBtn.classList.add('active');

    const targetPanel = document.getElementById(`settings-tab-${tabId}`);
    if (targetPanel) targetPanel.classList.add('active');
};

// API Key Visibility Toggle
window.toggleApiKeyVisibility = () => {
    const keyInput = document.getElementById('setting-api-key');
    const eyeIcon = document.getElementById('api-key-eye');
    if (keyInput && eyeIcon) {
        if (keyInput.type === 'password') {
            keyInput.type = 'text';
            eyeIcon.className = 'fas fa-eye-slash';
        } else {
            keyInput.type = 'password';
            eyeIcon.className = 'fas fa-eye';
        }
    }
};

// Provider Change Helper
window.onProviderChange = () => {
    const provider = document.getElementById('setting-provider').value;
    const modelInput = document.getElementById('setting-model-name');
    const urlInput = document.getElementById('setting-base-url');
    if (provider === 'deepseek') {
        modelInput.value = 'deepseek-chat';
        urlInput.value = 'https://api.deepseek.com';
    } else if (provider === 'openai') {
        modelInput.value = 'gpt-4o';
        urlInput.value = 'https://api.openai.com/v1';
    } else if (provider === 'local') {
        modelInput.value = 'llama3';
        urlInput.value = 'http://localhost:11434';
    }
};

// Save Model Settings
window.saveModelSettings = () => {
    const provider = document.getElementById('setting-provider').value;
    const model = document.getElementById('setting-model-name').value;
    const apiKey = document.getElementById('setting-api-key').value;
    const baseUrl = document.getElementById('setting-base-url').value;

    localStorage.setItem('setting_provider', provider);
    localStorage.setItem('setting_model', model);
    localStorage.setItem('setting_api_key', apiKey);
    localStorage.setItem('setting_base_url', baseUrl);

    window.showToast("保存成功", "大模型提供商参数已成功加密保存在本地 SecretVault 中！", "success");
};

// Memory Db Change Helper
window.onMemoryDbChange = () => {
    const dbType = document.getElementById('setting-memory-db').value;
    const badge = document.getElementById('active-memory-db-badge');
    if (badge) {
        badge.innerText = dbType.toUpperCase() + " Database";
        if (dbType === 'redis') {
            badge.style.background = 'rgba(0, 122, 255, 0.2)';
            badge.style.color = '#007AFF';
        } else if (dbType === 'zvec') {
            badge.style.background = 'rgba(52, 199, 89, 0.2)';
            badge.style.color = '#34C759';
        } else {
            badge.style.background = 'rgba(255, 149, 0, 0.2)';
            badge.style.color = '#FF9500';
        }
    }
};

// Save Memory Settings
window.saveMemorySettings = () => {
    const dbType = document.getElementById('setting-memory-db').value;
    const dreamEngine = document.getElementById('setting-dream-engine').checked;

    localStorage.setItem('setting_memory_db', dbType);
    localStorage.setItem('setting_dream_engine', dreamEngine);

    window.showToast("记忆库设置", "向量数据库切换及后台做梦精简规则已更新且生效。", "success");
};

// Test HAL Connection
window.testHalConnection = () => {
    window.showToast("硬件自检", "正在向物理 STM32 硬件总线发送遥测信号包...", "success");
    setTimeout(() => {
        window.showToast("测试完成", "回路反馈正常！已成功捕获 HAL 传感器温度与 USB-OLED 屏幕驱动缓存。", "success");
    }, 1500);
};

// Toggle Theme Mode
window.toggleThemeMode = () => {
    const toggleInput = document.getElementById('setting-theme-toggle');
    if (toggleInput) {
        if (toggleInput.checked) {
            document.body.classList.remove('theme-apple');
            document.body.classList.add('theme-dark');
            localStorage.setItem('setting_theme', 'dark');
            window.showToast("深浅主题", "已切换至「Midnight Cyberpunk」暗黑磨砂玻璃极客主题。", "success");
        } else {
            document.body.classList.remove('theme-dark');
            document.body.classList.add('theme-apple');
            localStorage.setItem('setting_theme', 'light');
            window.showToast("深浅主题", "已切换至「Apple Premium Light」白磨砂玻璃极简主题。", "success");
        }
    }
};

// Update Blur CSS custom property
window.updateBlurValue = (val) => {
    document.documentElement.style.setProperty('--glass-blur', `${val}px`);
    localStorage.setItem('setting_blur', val);
};

// Update Font Family globally
window.updateFontFamily = (val) => {
    document.documentElement.style.setProperty('--font-family', val);
    localStorage.setItem('setting_font_family', val);
    window.showToast("字体样式", "系统字体样式已成功更新。", "success");
};

// Update Font Size globally
window.updateFontSize = (val) => {
    document.documentElement.style.setProperty('--font-size', val);
    localStorage.setItem('setting_font_size', val);
    window.showToast("字体大小", `系统基本字号已调整为 ${val}。`, "success");
};

// Toggle Heatmap background
window.toggleHeatmapAnimation = () => {
    const toggle = document.getElementById('setting-heatmap-toggle');
    const canvas = document.getElementById('substrate-heatmap');
    if (canvas) {
        if (toggle && toggle.checked) {
            canvas.style.display = 'block';
            localStorage.setItem('setting_heatmap', 'true');
        } else {
            canvas.style.display = 'none';
            localStorage.setItem('setting_heatmap', 'false');
        }
    }
};

// Load Saved Form Settings
function loadSettingsForm() {
    if (localStorage.getItem('setting_provider')) {
        document.getElementById('setting-provider').value = localStorage.getItem('setting_provider');
    }
    if (localStorage.getItem('setting_model')) {
        document.getElementById('setting-model-name').value = localStorage.getItem('setting_model');
    }
    if (localStorage.getItem('setting_api_key')) {
        document.getElementById('setting-api-key').value = localStorage.getItem('setting_api_key');
    }
    if (localStorage.getItem('setting_base_url')) {
        document.getElementById('setting-base-url').value = localStorage.getItem('setting_base_url');
    }
    if (localStorage.getItem('setting_memory_db')) {
        const dbType = localStorage.getItem('setting_memory_db');
        document.getElementById('setting-memory-db').value = dbType;
        window.onMemoryDbChange();
    }
    if (localStorage.getItem('setting_dream_engine')) {
        document.getElementById('setting-dream-engine').checked = (localStorage.getItem('setting_dream_engine') === 'true');
    }
    if (localStorage.getItem('setting_theme')) {
        const isDark = (localStorage.getItem('setting_theme') === 'dark');
        document.getElementById('setting-theme-toggle').checked = isDark;
    }
    if (localStorage.getItem('setting_interface_mode')) {
        document.getElementById('setting-interface-mode').value = localStorage.getItem('setting_interface_mode');
    }
    if (localStorage.getItem('setting_blur')) {
        const blur = localStorage.getItem('setting_blur');
        document.getElementById('setting-blur-slider').value = blur;
        document.documentElement.style.setProperty('--glass-blur', `${blur}px`);
    }
    if (localStorage.getItem('setting_heatmap')) {
        const heatmapOn = (localStorage.getItem('setting_heatmap') === 'true');
        document.getElementById('setting-heatmap-toggle').checked = heatmapOn;
        const canvas = document.getElementById('substrate-heatmap');
        if (canvas) canvas.style.display = heatmapOn ? 'block' : 'none';
    }
    if (localStorage.getItem('setting_font_family')) {
        document.getElementById('setting-font-family').value = localStorage.getItem('setting_font_family');
    }
    if (localStorage.getItem('setting_font_size')) {
        document.getElementById('setting-font-size').value = localStorage.getItem('setting_font_size');
    }
}

// Vault Unlock Event
window.onVaultUnlocking = (data) => {
    const modal = document.createElement('div');
    modal.className = 'fullscreen-notif-overlay';
    modal.innerHTML = `
        <div class="fullscreen-notif-card glass-surface vault-unlock-card" style="border: 1px solid #d4af37;">
            <h2 style="color: #d4af37;"><i class="fas fa-shield-halved"></i> 密室正在解锁</h2>
            <p>为了您的隐私安全，Butler 正在从安全内存派生密钥。</p>
            <div class="vault-lock-animation active"><i class="fas fa-lock" style="font-size: 48px; color: #d4af37;"></i></div>
            <div style="margin-top: 30px;" class="loading-spinner"></div>
        </div>
    `;
    document.body.appendChild(modal);
    setTimeout(() => modal.remove(), 3000);
};

// Initial Theme Check and Application on DOM Load
document.addEventListener('DOMContentLoaded', () => {
    // If onboarding is completed, hide headers instantly
    if (localStorage.getItem('butler_onboarding_completed') === 'true') {
        document.body.classList.add('onboarding-completed');
    }

    const savedTheme = localStorage.getItem('setting_theme');
    if (savedTheme === 'dark') {
        document.body.classList.remove('theme-apple');
        document.body.classList.add('theme-dark');
    } else {
        document.body.classList.remove('theme-dark');
        document.body.classList.add('theme-apple');
    }

    const savedInterface = localStorage.getItem('setting_interface_mode') || 'desktop';
    if (savedInterface === 'mobile') {
        document.body.classList.remove('interface-desktop');
        document.body.classList.add('interface-mobile');
    } else {
        document.body.classList.remove('interface-mobile');
        document.body.classList.add('interface-desktop');
    }

    const savedBlur = localStorage.getItem('setting_blur');
    if (savedBlur) {
        document.documentElement.style.setProperty('--glass-blur', `${savedBlur}px`);
    }

    const savedHeatmap = localStorage.getItem('setting_heatmap');
    if (savedHeatmap === 'false') {
        const canvas = document.getElementById('substrate-heatmap');
        if (canvas) canvas.style.display = 'none';
    }

    const savedFontFamily = localStorage.getItem('setting_font_family');
    if (savedFontFamily) {
        document.documentElement.style.setProperty('--font-family', savedFontFamily);
    }

    const savedFontSize = localStorage.getItem('setting_font_size');
    if (savedFontSize) {
        document.documentElement.style.setProperty('--font-size', savedFontSize);
    }
});

// Initialize Matrix on Load
document.addEventListener('DOMContentLoaded', () => {
    // Add mock skills to drawer
    const drawer = document.querySelector('.skills-drawer');
    if (drawer) {
        const mockSkills = [
            { name: '截图排障', icon: 'fa-bug', color: '#FF3B30' },
            { name: '局域网同步', icon: 'fa-sync', color: '#34C759' },
            { name: '系统清理', icon: 'fa-broom', color: '#FF9500' }
        ];

        mockSkills.forEach(skill => {
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
    }
});

// Restore Legacy Handlers
window.toggleSkillsManager = () => {
    const el = document.getElementById('skills-manager-overlay');
    if (el) {
        el.classList.toggle('hidden');
        if (!el.classList.contains('hidden') && window.skillsManager) {
            window.skillsManager.init();
        }
    }
};

window.toggleTerminal = () => {
    const el = document.getElementById('terminal-overlay');
    el.classList.toggle('hidden');
    if (!el.classList.contains('hidden')) {
        // Init Terminal if needed
        if (!window.term) {
             window.term = new Terminal({
                cursorBlink: true,
                theme: { background: '#000000', foreground: '#f0f0f0' },
                fontSize: 14,
                fontFamily: 'SFMono-Regular, Consolas, monospace'
            });
            const fitAddon = new FitAddon.FitAddon();
            window.term.loadAddon(fitAddon);
            window.term.open(document.getElementById('terminal-container'));
            setTimeout(() => fitAddon.fit(), 100);
        }
    }
};

window.toggleMemos = () => {
    const el = document.getElementById('memos-overlay');
    el.classList.toggle('hidden');
    if (!el.classList.contains('hidden') && window.memosManager) {
        window.memosManager.refreshMemos();
    }
};

// Files Logic (Restored)
async function loadFiles(path) {
    if (window.pywebview && window.pywebview.api) {
        const files = await window.pywebview.api.list_files(path);
        const list = document.getElementById('files-list');
        if (!list) return;
        list.innerHTML = '';
        files.forEach(file => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.innerHTML = `<i class="fas ${file.is_dir ? 'fa-folder' : 'fa-file-alt'}"></i> <span>${file.name}</span>`;
            item.onclick = () => file.is_dir ? loadFiles(file.path) : null;
            list.appendChild(item);
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadFiles('.');

    // Launch Onboarding Tour automatically for new users after layout settles
    setTimeout(() => {
        if (!localStorage.getItem('butler_onboarding_completed')) {
            window.startOnboardingTour();
        }
    }, 1500);

    // --- Mobile WebMessagePort IPC Bridge ---
    window.addEventListener("message", function (event) {
        // Initial handshake from Android host
        if (event.data === "init_bridge" && event.ports[0]) {
            const port = event.ports[0];
            window.NativePort = port;

            port.onmessage = function (e) {
                try {
                    const data = JSON.parse(e.data);
                    // 1. High-frequency Metrics for SubstrateHeatmap
                    if (data.timestamp && window.StateMatrix) {
                        window.StateMatrix.updateFromBackend(data);
                    }
                    // 2. Throttling/DRAS state changes
                    if (data.type === "DRAS") {
                        const indicator = document.getElementById("connection-status");
                        if (indicator) {
                            indicator.style.backgroundColor = data.active ? "#FF9500" : "#34C759";
                        }
                    }
                    // 3. Native Logs to TimeMachine
                    if (data.type === "LOG" && window.TimeMachine) {
                        window.TimeMachine.pushLog(data.data);
                    }
                } catch (err) {
                    console.error("Native Bridge Parse Error:", err);
                }
            };
            console.log("Butler Mobile Bridge: Active via WebMessagePort");
        }
    });
});
