document.addEventListener('DOMContentLoaded', () => {
    // Navigation Elements
    const navItems = {
        chat: document.getElementById('nav-chat'),
        terminal: document.getElementById('nav-terminal'),
        workspace: document.getElementById('nav-workspace'),
        files: document.getElementById('nav-files'),
        settings: document.getElementById('nav-settings')
    };

    const views = {
        chat: document.getElementById('view-chat'),
        terminal: document.getElementById('view-terminal'),
        workspace: document.getElementById('view-workspace'),
        files: document.getElementById('view-files'),
        settings: document.getElementById('view-settings')
    };

    const viewTitle = document.getElementById('current-view-title');
    const interactionFlow = document.getElementById('interaction-flow');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-command-btn');
    const voiceToggleBtn = document.getElementById('voice-toggle-btn');

    // State
    let isStreaming = false;
    let currentAILine = null;
    let lastUserCommand = "";

    // Terminal initialization
    const term = new Terminal({
        cursorBlink: true,
        theme: { background: '#000000', foreground: '#f0f0f0' },
        fontSize: 14,
        fontFamily: 'SFMono-Regular, Consolas, monospace'
    });
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(document.getElementById('terminal-container'));

    // Fit terminal on switch
    const fitTerminal = () => {
        setTimeout(() => fitAddon.fit(), 100);
    };

    term.onData(data => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.terminal_input(data);
        }
    });

    // View Switching Logic
    function switchView(viewName) {
        Object.keys(views).forEach(key => {
            views[key].classList.remove('active');
            navItems[key].classList.remove('active');
        });

        views[viewName].classList.add('active');
        navItems[viewName].classList.add('active');

        const titles = {
            chat: '智能助手',
            terminal: '终端会话',
            workspace: '全屏工作区',
            files: '文件管理',
            settings: '系统设置'
        };
        viewTitle.innerText = titles[viewName];

        if (viewName === 'terminal') {
            fitTerminal();
            if (window.pywebview && window.pywebview.api) window.pywebview.api.start_terminal();
        } else if (viewName === 'files') {
            loadFiles('.');
        }
    }

    Object.keys(navItems).forEach(key => {
        navItems[key].addEventListener('click', () => switchView(key));
    });

    // Chat Logic
    function executeChatCommand() {
        const command = chatInput.innerText.trim();
        if (!command || isStreaming) return;

        // Hide welcome on first interaction
        const welcome = document.querySelector('.welcome-message');
        if (welcome) welcome.style.display = 'none';

        // Add user bubble
        const userLine = document.createElement('div');
        userLine.className = 'interaction-line user-input-line';
        userLine.innerText = command;
        interactionFlow.appendChild(userLine);

        lastUserCommand = command;
        chatInput.innerText = "";
        isStreaming = true;

        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.handle_command(command);
        } else {
            // Mock response
            onAIStreamStart();
            onAIStreamChunk("您当前处于演示模式。输入的命令是: " + command);
            onAIStreamEnd();
        }

        interactionFlow.scrollTop = interactionFlow.scrollHeight;
    }

    sendBtn.addEventListener('click', executeChatCommand);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            executeChatCommand();
        }
    });

    // Bridge Functions
    window.onAIStreamStart = () => {
        isStreaming = true;
        document.getElementById('thinking-status').classList.add('active');

        currentAILine = document.createElement('div');
        currentAILine.className = 'interaction-line ai-output-line';
        interactionFlow.appendChild(currentAILine);
        interactionFlow.scrollTop = interactionFlow.scrollHeight;
    };

    window.onAIStreamChunk = (chunk) => {
        if (currentAILine) {
            try {
                const data = JSON.parse(chunk);
                if (data.type === 'media') {
                    renderMediaInChat(data);
                    return;
                } else if (data.type === 'translation') {
                    renderTranslationInChat(data);
                    return;
                } else if (data.type === 'code_block') {
                    renderCodeBlockInChat(data);
                    return;
                } else if (data.type === 'quota_report') {
                    renderQuotaInChat(data);
                    return;
                }
            } catch (e) {}

            const textSpan = document.createElement('span');
            textSpan.innerText = chunk;
            currentAILine.appendChild(textSpan);
            interactionFlow.scrollTop = interactionFlow.scrollHeight;
        }
    };

    function renderTranslationInChat(data) {
        const container = document.createElement('div');
        container.className = 'translation-container';

        const header = document.createElement('div');
        header.style.display = 'flex';
        header.style.justifyContent = 'space-between';
        header.style.marginBottom = '15px';

        const info = document.createElement('div');
        info.innerHTML = `<div style="font-weight: 600;">${data.metadata.title || '翻译结果'}</div><div style="font-size: 12px; opacity: 0.6;">${data.metadata.source_title || ''}</div>`;

        const laIcon = document.createElement('div');
        laIcon.className = 'translation-la-icon';
        laIcon.innerText = 'LA';

        header.appendChild(info);
        header.appendChild(laIcon);
        container.appendChild(header);

        data.data.forEach(item => {
            const segment = document.createElement('div');
            segment.style.marginBottom = '12px';
            segment.innerHTML = `<div style="font-size: 14px; opacity: 0.8;">${item.source}</div><div class="segment-target">${item.target}</div>`;
            container.appendChild(segment);
        });

        currentAILine.appendChild(container);
    }

    function renderCodeBlockInChat(data) {
        const block = document.createElement('div');
        block.className = 'code-block';

        const header = document.createElement('div');
        header.className = 'code-header';
        header.innerHTML = `<span>${data.language.toUpperCase()}</span><i class="fas fa-copy" style="cursor:pointer"></i>`;

        const content = document.createElement('div');
        content.className = 'code-content';
        content.innerText = data.code;

        block.appendChild(header);
        block.appendChild(content);
        currentAILine.appendChild(block);
    }

    function renderQuotaInChat(data) {
        const card = document.createElement('div');
        card.className = 'ai-output-line';
        card.style.borderLeft = '4px solid #FF9500';
        card.style.background = 'rgba(255, 149, 0, 0.05)';
        card.style.padding = '20px';
        card.style.marginTop = '15px';

        card.innerHTML = `
            <div style="font-weight: 600; color: #FF9500; margin-bottom: 15px;">系统配额报告</div>
            <div style="display: flex; flex-direction: column; gap: 10px;">
                ${data.items.map(item => `
                    <div style="font-size: 14px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                            <span>${item.name}</span>
                            <span>${item.used} / ${item.total}</span>
                        </div>
                        <div style="height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px;">
                            <div style="height: 100%; width: ${(item.used / item.total * 100).toFixed(1)}%; background: #FF9500; border-radius: 2px;"></div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
        currentAILine.appendChild(card);
    }

    window.onAIStreamEnd = () => {
        isStreaming = false;
        document.getElementById('thinking-status').classList.remove('active');
    };

    window.onTerminalOutput = (data) => term.write(data);

    // Media and Special Components
    function renderMediaInChat(data) {
        const container = document.createElement('div');
        container.className = 'chat-media-item';
        container.style.marginTop = '12px';
        container.style.cursor = 'pointer';

        if (data.media_type === 'image') {
            const img = document.createElement('img');
            img.src = data.url;
            img.style.maxWidth = '100%';
            img.style.borderRadius = '12px';
            container.appendChild(img);
        } else {
            const placeholder = document.createElement('div');
            placeholder.className = 'ai-output-line';
            placeholder.innerHTML = `<i class="fas fa-play-circle"></i> <span>查看媒体: ${data.title || '文件'}</span>`;
            container.appendChild(placeholder);
        }

        container.onclick = () => openMediaGallery(data);
        currentAILine.appendChild(container);
    }

    function openMediaGallery(data) {
        const overlay = document.getElementById('media-overlay');
        const content = document.getElementById('media-content');
        const title = document.getElementById('media-title');

        content.innerHTML = '';
        title.innerText = data.title || '预览';

        if (data.media_type === 'image') {
            const img = document.createElement('img');
            img.src = data.url;
            content.appendChild(img);
        } else if (data.media_type === 'video') {
            const v = document.createElement('video');
            v.src = data.url;
            v.controls = v.autoplay = true;
            content.appendChild(v);
        }

        overlay.classList.remove('hidden');
    }

    document.getElementById('close-media').onclick = () => {
        document.getElementById('media-overlay').classList.add('hidden');
        document.getElementById('media-content').innerHTML = '';
    };

    // Files Logic
    async function loadFiles(path) {
        if (window.pywebview && window.pywebview.api) {
            const files = await window.pywebview.api.list_files(path);
            renderFiles(files);
        }
    }

    function renderFiles(files) {
        const list = document.getElementById('files-list');
        list.innerHTML = '';

        files.forEach(file => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.innerHTML = `
                <i class="fas ${file.is_dir ? 'fa-folder' : 'fa-file-alt'}"></i>
                <span>${file.name}</span>
            `;

            item.onclick = () => {
                if (file.is_dir) {
                    loadFiles(file.path);
                } else if (isOfficeDoc(file.name)) {
                    previewDocument(file);
                }
            };
            list.appendChild(item);
        });
    }

    function isOfficeDoc(name) {
        const ext = name.split('.').pop().toLowerCase();
        return ['pdf', 'docx', 'xlsx', 'pptx', 'txt', 'md'].includes(ext);
    }

    async function previewDocument(file) {
        switchView('workspace');
        const placeholder = document.querySelector('.workspace-placeholder');
        const viewer = document.getElementById('document-viewer');
        const content = document.getElementById('viewer-content');
        const fileName = document.getElementById('viewer-filename');

        placeholder.classList.add('hidden');
        viewer.classList.remove('hidden');
        fileName.innerText = file.name;
        content.innerHTML = '<div class="loading">正在加载文档内容...</div>';

        // Mock document preview logic
        setTimeout(() => {
            content.innerHTML = `<h3>${file.name} 预览</h3><p>由于沙盒环境限制，此处显示模拟内容。实际环境中将调用后端转换接口显示 PDF 或 HTML 渲染内容。</p>`;
        }, 800);
    }

    document.getElementById('viewer-close').onclick = () => {
        document.getElementById('document-viewer').classList.add('hidden');
        document.querySelector('.workspace-placeholder').classList.remove('hidden');
    };

    // Init
    window.addEventListener('resize', fitTerminal);

    // Auto-focus chat input
    chatInput.focus();
    document.addEventListener('click', (e) => {
        if (views.chat.classList.contains('active') && !e.target.closest('.sidebar')) {
            chatInput.focus();
        }
    });

    // Theme loading
    const savedBg = localStorage.getItem('butler-custom-bg');
    if (savedBg) document.body.style.backgroundImage = `url(${savedBg})`;
});
