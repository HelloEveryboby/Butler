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
    // Navigation Elements
    const navItems = {
        chat: document.getElementById('nav-chat'),
        terminal: document.getElementById('nav-terminal'),
        workspace: document.getElementById('nav-workspace'),
        media: document.getElementById('nav-media'),
        files: document.getElementById('nav-files'),
        memos: document.getElementById('nav-memos'),
        screenshot: document.getElementById('nav-screenshot'),
        settings: document.getElementById('nav-settings')
    };

    const views = {
        chat: document.getElementById('view-chat'),
        terminal: document.getElementById('view-terminal'),
        workspace: document.getElementById('view-workspace'),
        media: document.getElementById('view-media'),
        files: document.getElementById('view-files'),
        memos: document.getElementById('view-memos'),
        screenshot: document.getElementById('view-chat'), // Overlay mode
        settings: document.getElementById('view-settings')
    };

    const viewTitle = document.getElementById('current-view-title');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const bgUploadBtn = document.getElementById('bg-upload-btn');
    const bgUploadInput = document.getElementById('bg-upload');
    const appContainer = document.querySelector('.app-container');
    const interactionFlow = document.getElementById('interaction-flow');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-command-btn');
    const voiceToggleBtn = document.getElementById('voice-toggle-btn');
    const voiceStatusDot = document.getElementById('voice-status');

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
            media: '多媒体中心',
            files: '文件管理',
            memos: '备忘录',
            screenshot: '高级截图',
            settings: '系统设置'
        };
        viewTitle.innerText = titles[viewName];

        if (viewName === 'terminal') {
            fitTerminal();
            if (window.pywebview && window.pywebview.api) window.pywebview.api.start_terminal();
        } else if (viewName === 'files') {
            loadFiles('.');
        } else if (viewName === 'media') {
            loadMediaLibrary();
        } else if (viewName === 'screenshot') {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.handle_command("/screenshot-overlay");
                setTimeout(() => switchView('chat'), 500);
            }
        }
    }

    Object.keys(navItems).forEach(key => {
        navItems[key].addEventListener('click', () => switchView(key));
    });

    // Sidebar Toggle Persistence
    const isSidebarHidden = localStorage.getItem('butler-sidebar-hidden') === 'true';
    if (isSidebarHidden) appContainer.classList.add('sidebar-hidden');

    sidebarToggle.addEventListener('click', () => {
        appContainer.classList.toggle('sidebar-hidden');
        const isHidden = appContainer.classList.contains('sidebar-hidden');
        localStorage.setItem('butler-sidebar-hidden', isHidden);
        // Fit terminal if active
        if (views.terminal.classList.contains('active')) fitTerminal();
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

    voiceToggleBtn.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.handle_command("/voice-toggle");
        }
    });

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
        const titleEl = document.createElement('div');
        titleEl.style.fontWeight = '600';
        titleEl.textContent = data.metadata.title || '翻译结果';
        const sourceTitleEl = document.createElement('div');
        sourceTitleEl.style.fontSize = '12px';
        sourceTitleEl.style.opacity = '0.6';
        sourceTitleEl.textContent = data.metadata.source_title || '';
        info.appendChild(titleEl);
        info.appendChild(sourceTitleEl);

        const laIcon = document.createElement('div');
        laIcon.className = 'translation-la-icon';
        laIcon.innerText = 'LA';

        header.appendChild(info);
        header.appendChild(laIcon);
        container.appendChild(header);

        data.data.forEach(item => {
            const segment = document.createElement('div');
            segment.style.marginBottom = '12px';

            const sourceEl = document.createElement('div');
            sourceEl.style.fontSize = '14px';
            sourceEl.style.opacity = '0.8';
            sourceEl.textContent = item.source;

            const targetEl = document.createElement('div');
            targetEl.className = 'segment-target';
            targetEl.textContent = item.target;

            segment.appendChild(sourceEl);
            segment.appendChild(targetEl);
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
                            <span>${window.escapeHTML(item.name)}</span>
                            <span>${window.escapeHTML(String(item.used))} / ${window.escapeHTML(String(item.total))}</span>
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

    window.onVoiceStatusChange = (isListening) => {
        if (isListening) {
            voiceStatusDot.classList.add('active');
            voiceToggleBtn.classList.add('active');
        } else {
            voiceStatusDot.classList.remove('active');
            voiceToggleBtn.classList.remove('active');
        }
    };

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
            placeholder.innerHTML = `<i class="fas fa-play-circle"></i> <span>查看媒体: ${window.escapeHTML(data.title || '文件')}</span>`;
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

            const icon = document.createElement('i');
            icon.className = `fas ${file.is_dir ? 'fa-folder' : 'fa-file-alt'}`;
            const name = document.createElement('span');
            name.textContent = file.name;

            item.appendChild(icon);
            item.appendChild(name);

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

    window.previewDocument = async function(file) {
        switchView('workspace');
        const placeholder = document.querySelector('.workspace-placeholder');
        const viewer = document.getElementById('document-viewer');
        const content = document.getElementById('viewer-content');
        const fileName = document.getElementById('viewer-filename');

        placeholder.classList.add('hidden');
        viewer.classList.remove('hidden');
        fileName.innerText = file.name;
        content.innerHTML = '<div class="loading">正在加载文档内容...</div>';

        const ext = file.name.split('.').pop().toLowerCase();

        if (ext === 'pdf') {
            try {
                const b64Data = await window.pywebview.api.get_file_base64(file.path);
                const binaryData = atob(b64Data);
                const uint8Array = new Uint8Array(binaryData.length);
                for (let i = 0; i < binaryData.length; i++) {
                    uint8Array[i] = binaryData.charCodeAt(i);
                }

                content.innerHTML = '<div id="pdf-container" style="display: flex; flex-direction: column; gap: 20px; align-items: center; padding: 20px;"></div>';
                const container = document.getElementById('pdf-container');
                const loadingTask = pdfjsLib.getDocument({ data: uint8Array });
                const pdf = await loadingTask.promise;

                for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
                    const page = await pdf.getPage(pageNum);
                    const scale = 1.5;
                    const viewport = page.getViewport({ scale });

                    const canvas = document.createElement('canvas');
                    canvas.style.width = '100%';
                    canvas.style.maxWidth = '800px';
                    canvas.style.borderRadius = '4px';
                    canvas.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
                    container.appendChild(canvas);

                    const context = canvas.getContext('2d');
                    canvas.height = viewport.height;
                    canvas.width = viewport.width;

                    await page.render({ canvasContext: context, viewport }).promise;
                }
            } catch (e) {
                content.innerHTML = `<div class="error">加载 PDF 失败: ${window.escapeHTML(e.message)}</div>`;
            }
        } else if (ext === 'txt' || ext === 'md') {
            try {
                const b64Data = await window.pywebview.api.get_file_base64(file.path);
                const text = decodeURIComponent(escape(atob(b64Data)));
                const pre = document.createElement('pre');
                pre.style.cssText = "white-space: pre-wrap; padding: 20px; font-family: 'Inter', sans-serif;";
                pre.textContent = text;
                content.innerHTML = '';
                content.appendChild(pre);
            } catch (e) {
                content.innerHTML = `<div class="error">加载文本失败: ${window.escapeHTML(e.message)}</div>`;
            }
        } else {
            content.innerHTML = `<h3>${window.escapeHTML(file.name)} 预览</h3><p>目前仅支持 PDF 和 文本文件在线预览。其他格式请使用对应技能进行处理。</p>`;
        }
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

    // Background Logic
    bgUploadBtn.addEventListener('click', () => bgUploadInput.click());

    bgUploadInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (event) => {
                const dataUrl = event.target.result;
                applyBackground(dataUrl);
                localStorage.setItem('butler-custom-bg', dataUrl);
            };
            reader.readAsDataURL(file);
        }
    });

    function applyBackground(dataUrl) {
        if (dataUrl) {
            document.body.style.backgroundImage = `url(${dataUrl})`;
            document.body.classList.add('has-custom-bg');
        } else {
            document.body.style.backgroundImage = '';
            document.body.classList.remove('has-custom-bg');
        }
    }

    // Media Center Logic
    let mediaLibrary = [];
    let currentMediaFilter = 'audio';

    async function loadMediaLibrary() {
        if (window.pywebview && window.pywebview.api) {
            // Assume we'll have a get_media_library method in the API
            const library = await window.pywebview.api.get_media_library();
            mediaLibrary = library;
            renderMediaLibrary();
        } else {
            // Mock data
            mediaLibrary = [
                { name: 'Example Music.mp3', path: 'assets/music/example.mp3', type: 'audio' },
                { name: 'Sample Audio.wav', path: 'assets/music/sample.wav', type: 'audio' },
                { name: 'Beautiful Landscape.jpg', path: 'assets/images/landscape.jpg', type: 'image' },
                { name: 'Portrait.jpg', path: 'assets/images/portrait.jpg', type: 'image' }
            ];
            renderMediaLibrary();
        }
    }

    function renderMediaLibrary() {
        const listContainer = document.getElementById('media-list');
        listContainer.innerHTML = '';

        const filtered = mediaLibrary.filter(item => {
            if (currentMediaFilter === 'audio') return item.name.toLowerCase().endsWith('.mp3') || item.name.toLowerCase().endsWith('.wav');
            if (currentMediaFilter === 'image') return item.name.toLowerCase().endsWith('.jpg') || item.name.toLowerCase().endsWith('.jpeg');
            return true;
        });

        filtered.forEach(item => {
            const div = document.createElement('div');
            div.className = 'media-item-row';
            const icon = item.type === 'audio' ? 'fa-music' : 'fa-image';

            const iconEl = document.createElement('i');
            iconEl.className = `fas ${icon}`;
            const nameEl = document.createElement('span');
            nameEl.textContent = item.name;

            div.appendChild(iconEl);
            div.appendChild(nameEl);

            div.onclick = () => selectMediaItem(item);
            listContainer.appendChild(div);
        });
    }

    document.getElementById('media-filter-audio').onclick = () => {
        currentMediaFilter = 'audio';
        document.getElementById('media-filter-audio').classList.add('active');
        document.getElementById('media-filter-image').classList.remove('active');
        renderMediaLibrary();
    };

    document.getElementById('media-filter-image').onclick = () => {
        currentMediaFilter = 'image';
        document.getElementById('media-filter-image').classList.add('active');
        document.getElementById('media-filter-audio').classList.remove('active');
        renderMediaLibrary();
    };

    function selectMediaItem(item) {
        const audioCard = document.getElementById('audio-player-card');
        const imageCard = document.getElementById('image-viewer-card');
        const audioPlayer = document.getElementById('main-audio-player');
        const imageViewer = document.getElementById('main-image-viewer');
        const titleDisp = document.getElementById('media-title-display');
        const formatInfo = document.getElementById('format-info-content');

        if (item.type === 'audio') {
            audioCard.classList.remove('hidden');
            imageCard.classList.add('hidden');
            audioPlayer.src = item.path;
            audioPlayer.play();
            titleDisp.innerText = item.name;
            showFormatInfo(item.name.split('.').pop().toLowerCase());
        } else if (item.type === 'image') {
            audioCard.classList.add('hidden');
            imageCard.classList.remove('hidden');
            audioPlayer.pause();
            imageViewer.src = item.path;
            showFormatInfo('jpg');
        }
    }

    function showFormatInfo(ext) {
        const info = {
            'mp3': '<b>MP3 (MPEG-1 Audio Layer III)</b><br>由来：由德国 Fraunhofer 集成电路研究所开发。它是一种有损压缩音频格式，由于其极高的压缩比（约 1:10）和保持良好的音质，在 90 年代互联网早期迅速流行，彻底改变了音乐发行和存储方式。',
            'wav': '<b>WAV (Waveform Audio File Format)</b><br>由来：由微软与 IBM 联合开发，主要用于 Windows 系统。它通常存储无损、未压缩的音频数据，采用 PCM（脉冲编码调制）编码。虽然体积巨大，但它是专业音频编辑和高保真听感的标准格式。',
            'jpg': '<b>JPG / JPEG (Joint Photographic Experts Group)</b><br>由来：由联合图像专家小组于 1992 年发布。它是针对彩色照片进行的有损压缩标准，利用了人类视觉对色彩变化敏感度低于亮度变化的特性。它是目前互联网上使用最广泛的图片格式。',
            'jpeg': '<b>JPEG</b><br>由来：同 JPG。JPEG 是该标准的完整缩写。'
        };
        document.getElementById('format-info-content').innerHTML = info[ext] || '未知格式背景信息。';
    }

    // Random Shuffle Logic
    document.getElementById('shuffle-media-btn').onclick = () => {
        const audios = mediaLibrary.filter(item => item.name.toLowerCase().endsWith('.mp3') || item.name.toLowerCase().endsWith('.wav'));
        if (audios.length > 0) {
            const randomIndex = Math.floor(Math.random() * audios.length);
            selectMediaItem(audios[randomIndex]);
        }
    };

    // Load saved background on startup
    const savedBg = localStorage.getItem('butler-custom-bg');
    if (savedBg) applyBackground(savedBg);

    // --- Notifier System Integration ---
    window.onNotificationPush = (event) => {
        if (event.priority >= 2) {
            renderFullscreenNotification(event);
        } else {
            renderToastNotification(event);
        }
    };

    window.onFocusStart = (msg) => {
        const overlay = document.createElement('div');
        overlay.className = 'fullscreen-notif-overlay focus-overlay';
        overlay.id = 'focus-mode-overlay';
        overlay.innerHTML = `
            <div class="fullscreen-notif-card" style="background: rgba(10, 10, 10, 0.9); border: 1px solid #007AFF;">
                <i class="fas fa-hourglass-half" style="font-size: 48px; color: #007AFF; margin-bottom: 20px;"></i>
                <h2>沉浸学习模式已开启</h2>
                <p style="font-size: 18px; margin-bottom: 30px;">${window.escapeHTML(msg)}</p>
                <div class="focus-timer" style="font-size: 32px; font-weight: bold; margin-bottom: 30px;" id="focus-countdown">--:--</div>
                <button class="apple-btn-primary" style="background: rgba(255, 59, 48, 0.2); color: #ff3b30;" onclick="window.pywebview.api.handle_command('/focus-stop')">结束专注</button>
            </div>
        `;
        document.body.appendChild(overlay);

        // Start a local UI timer for display
        let seconds = 25 * 60; // Default or extract from msg
        if (msg.includes('started')) {
            const match = msg.match(/(\d+)m/);
            if (match) seconds = parseInt(match[1]) * 60;
        }

        const updateTimer = () => {
            if (!document.getElementById('focus-mode-overlay')) return;
            const m = Math.floor(seconds / 60);
            const s = seconds % 60;
            document.getElementById('focus-countdown').innerText = `${m}:${s < 10 ? '0' : ''}${s}`;
            if (seconds > 0) {
                seconds--;
                setTimeout(updateTimer, 1000);
            }
        };
        updateTimer();
    };

    window.onFocusStop = () => {
        const el = document.getElementById('focus-mode-overlay');
        if (el) {
            el.classList.add('closing');
            setTimeout(() => el.remove(), 400);
        }
    };

    window.onNotificationClose = (data) => {
        const el = document.getElementById(data.id);
        if (el) {
            el.classList.add('closing');
            setTimeout(() => el.remove(), 400);
        }

        const overlay = document.getElementById('fullscreen-overlay-' + data.id);
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.remove(), 400);
        }
    };

    function renderToastNotification(event) {
        const root = document.getElementById('notifier-root');
        const toast = document.createElement('div');
        toast.className = 'toast-notification';
        toast.id = event.id;

        toast.innerHTML = `
            <div class="breathing-glow"></div>
            <div class="notif-header">
                <span class="notif-time">${window.escapeHTML(event.timestamp.split(' ')[1])}</span>
                <i class="fas fa-times" style="cursor:pointer; font-size: 12px; color: var(--text-secondary);" onclick="window.onNotificationClose({id: '${event.id}'})"></i>
            </div>
            <div class="notif-title">${window.escapeHTML(event.title)}</div>
            <div class="notif-content">${window.escapeHTML(event.content)}</div>
        `;

        toast.onclick = () => {
            // Placeholder for clicking to modify data
            console.log("Modify notification:", event.id);
        };

        root.appendChild(toast);
    }

    function renderFullscreenNotification(event) {
        const overlay = document.createElement('div');
        overlay.className = 'fullscreen-notif-overlay';
        overlay.id = 'fullscreen-overlay-' + event.id;

        overlay.innerHTML = `
            <div class="fullscreen-notif-card">
                <div class="notif-time" style="margin-bottom: 20px;">${window.escapeHTML(event.timestamp)}</div>
                <h2>${window.escapeHTML(event.title)}</h2>
                <p>${window.escapeHTML(event.content)}</p>
                <div style="display: flex; gap: 15px; justify-content: center;">
                    <button class="apple-btn-primary" onclick="window.onNotificationClose({id: '${event.id}'})">确认并关闭</button>
                    <button class="apple-btn-primary" style="background: rgba(255,255,255,0.1); color: var(--text-primary);">稍后处理</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
    }
});

// --- Settings and Skill Management Extensions ---
document.addEventListener('DOMContentLoaded', () => {
    const themeSelector = document.getElementById('theme-selector');
    if (themeSelector) {
        themeSelector.addEventListener('change', (e) => {
            const theme = e.target.value;
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.handle_command(`/theme ${theme}`);
            }
        });
    }

    const skillInstallUrl = document.getElementById('skill-install-url');
    const skillInstallBtn = document.getElementById('skill-install-btn');
    const refreshSkillsBtn = document.getElementById('refresh-skills-btn');
    const skillsListContainer = document.getElementById('skills-list-container');

    async function loadSkillsList() {
        if (window.pywebview && window.pywebview.api) {
            skillsListContainer.innerHTML = '<p class="loading-text">正在加载技能列表...</p>';
            const report = await window.pywebview.api.get_skills_list();
            renderSkillsFromMarkdown(report);
        }
    }

    function renderSkillsFromMarkdown(report) {
        skillsListContainer.innerHTML = '';
        const lines = report.split('\n');

        lines.forEach(line => {
            if (line.startsWith('- **')) {
                const match = line.match(/- \*\*(.*?)\*\*: (.*?) \((.*?)\)/);
                if (match) {
                    const [_, name, desc, status] = match;
                    const item = document.createElement('div');
                    item.className = 'skill-ui-item';

                    item.innerHTML = `
                        <div class="skill-ui-info">
                            <div class="skill-ui-name">${window.escapeHTML(name)}</div>
                            <div class="skill-ui-desc">${window.escapeHTML(desc)}</div>
                        </div>
                        <div class="skill-ui-actions">
                            <span class="skill-status-tag">${window.escapeHTML(status)}</span>
                            ${['markitdown', 'xlsx_recalc', 'task_management'].includes(name) ?
                                '' :
                                `<button class="skill-uninstall-btn" onclick="uiUninstallSkill(${window.escapeHTML(JSON.stringify(name))})"><i class="fas fa-trash"></i></button>`}
                        </div>
                    `;
                    skillsListContainer.appendChild(item);
                }
            }
        });

        if (skillsListContainer.innerHTML === '') {
            skillsListContainer.innerHTML = '<p class="loading-text">未检测到已安装的技能。</p>';
        }
    }

    window.uiUninstallSkill = async (name) => {
        if (confirm(`确定要卸载技能 "${name}" 吗？`)) {
            const result = await window.pywebview.api.uninstall_skill(name);
            alert(result);
            loadSkillsList();
        }
    };

    if (skillInstallBtn) {
        skillInstallBtn.addEventListener('click', async () => {
            const url = skillInstallUrl.value.trim();
            if (!url) return alert('请输入技能 Git 链接');

            skillInstallBtn.disabled = true;
            skillInstallBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 安装中...';

            const result = await window.pywebview.api.install_skill(url);
            alert(result);

            skillInstallBtn.disabled = false;
            skillInstallBtn.innerHTML = '<i class="fas fa-download"></i> 安装';
            skillInstallUrl.value = '';
            loadSkillsList();
        });
    }

    if (refreshSkillsBtn) {
        refreshSkillsBtn.addEventListener('click', loadSkillsList);
    }

    // Settings Sub-navigation
    const settingsNavItems = document.querySelectorAll('.settings-nav-item');
    const settingsPanels = document.querySelectorAll('.settings-panel');
    const voiceEngineSelector = document.getElementById('voice-engine-selector');

    if (voiceEngineSelector) {
        voiceEngineSelector.addEventListener('change', async (e) => {
            if (window.pywebview && window.pywebview.api) {
                await window.pywebview.api.set_voice_engine(e.target.value);
            }
        });
    }

    settingsNavItems.forEach(item => {
        item.addEventListener('click', () => {
            const target = item.getAttribute('data-target');

            // Update Nav
            settingsNavItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // Update Panels
            settingsPanels.forEach(panel => panel.classList.remove('active'));
            document.getElementById(target).classList.add('active');

            // Trigger specific loads
            if (target === 'settings-skills') loadSkillsList();
            if (target === 'settings-quota') loadQuotaInfo();
        });
    });

    async function loadQuotaInfo() {
        const quotaDisplay = document.getElementById('quota-display');
        if (window.pywebview && window.pywebview.api) {
            // We'll use a hidden command to get quota if no direct API exists,
            // but usually we can trigger the quota report in chat or get it via API
            // For now, let's assume we can fetch it or show a placeholder that explains how to get it.
            quotaDisplay.innerHTML = '<p class="loading-text">正在从系统获取配额信息...</p>';

            // If the backend doesn't have get_quota_report, we might need to handle it.
            // Let's try to call it if it exists.
            try {
                if (window.pywebview.api.get_quota_report) {
                    const data = await window.pywebview.api.get_quota_report();
                    renderQuotaInSettings(data);
                } else {
                    quotaDisplay.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-secondary);">请在对话框输入 "/quota" 查看实时配额报告。</div>';
                }
            } catch (e) {
                quotaDisplay.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-secondary);">获取配额失败。</div>';
            }
        }
    }

    function renderQuotaInSettings(data) {
        const quotaDisplay = document.getElementById('quota-display');
        quotaDisplay.innerHTML = data.items.map(item => `
            <div class="settings-row">
                <div style="flex: 1;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <span class="row-label">${window.escapeHTML(item.name)}</span>
                        <span style="font-size: 12px; color: var(--text-secondary);">${window.escapeHTML(String(item.used))} / ${window.escapeHTML(String(item.total))}</span>
                    </div>
                    <div style="height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px;">
                        <div style="height: 100%; width: ${(item.used / item.total * 100).toFixed(1)}%; background: var(--accent-color); border-radius: 3px;"></div>
                    </div>
                </div>
            </div>
        `).join('');
    }

    // Override switchView to load initial settings data
    const navSettings = document.getElementById('nav-settings');
    if (navSettings) {
        navSettings.addEventListener('click', () => {
            // Default to general, but if we are already on another tab, stay there or refresh it
            const activeSubNav = document.querySelector('.settings-nav-item.active');
            if (activeSubNav) {
                const target = activeSubNav.getAttribute('data-target');
                if (target === 'settings-skills') loadSkillsList();
                if (target === 'settings-quota') loadQuotaInfo();
            }
        });
    }
});
