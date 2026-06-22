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
            container.querySelector('p').innerText = "诊断完成。";

            // Show Fix Card
            renderFixCard({
                type: 'PORT_OCCUPIED',
                title: '检测到端口 8080 被占用',
                desc: '当前端口 8080 正被 PID 1234 (Python) 占用，导致服务器无法启动。',
                btnText: '一键释放端口'
            });
        }, 2500);
    }

    function renderFixCard(data) {
        const card = document.createElement('div');
        card.className = 'fix-card';
        card.innerHTML = `
            <div style="font-weight: 700; color: #34C759; display: flex; align-items: center; gap: 8px;">
                <i class="fas fa-check-circle"></i> ${data.title}
            </div>
            <p style="font-size: 14px; opacity: 0.8;">${data.desc}</p>
            <button class="fix-btn">${data.btnText}</button>
        `;

        card.querySelector('.fix-btn').onclick = async () => {
            card.querySelector('.fix-btn').innerText = "修复中...";
            setTimeout(() => {
                card.innerHTML = `
                    <div style="color: #34C759; font-weight: 700;">
                        <i class="fas fa-magic"></i> 修复成功！端口已释放。
                    </div>
                `;
            }, 1500);
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
            window.pywebview.api.handle_command("/airdrop-out");
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

// Settings Toggle
window.toggleSettings = () => {
    document.getElementById('settings-overlay').classList.toggle('hidden');
};

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
    document.getElementById('memos-overlay').classList.toggle('hidden');
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
});
