document.addEventListener('DOMContentLoaded', () => {
    const interactionFlow = document.getElementById('interaction-flow');
    const terminalOverlay = document.getElementById('terminal-overlay');
    const closeTerminalBtn = document.getElementById('close-terminal');
    const statusBar = { innerText: "" }; // Replaced by header or nav bar feedback

    // Nav Bar Items
    const navHome = document.getElementById('nav-home');
    const navTerminal = document.getElementById('nav-terminal');
    const navVoice = document.getElementById('nav-voice');
    const navEditor = document.getElementById('nav-editor');
    const navSettings = document.getElementById('nav-settings');

    // Editor Components
    const editorOverlay = document.getElementById('editor-overlay');
    const closeEditorBtn = document.getElementById('close-editor');
    const markdownEditor = document.getElementById('markdown-editor');
    const saveEditorBtn = document.getElementById('save-editor');
    const openOfficeBtn = document.getElementById('open-in-office');
    const toolbarButtons = document.querySelectorAll('.toolbar-btn');

    let isStreaming = false;
    let currentAILine = null;
    let lastUserCommand = "";

    // Terminal initialization
    const term = new Terminal({
        cursorBlink: true,
        theme: {
            background: '#141414',
            foreground: '#f0f0f0'
        },
        fontSize: 14,
        fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace'
    });
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);

    term.open(document.getElementById('terminal-container'));
    setTimeout(() => fitAddon.fit(), 100);

    window.addEventListener('resize', () => fitAddon.fit());

    term.onData(data => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.terminal_input(data);
        }
    });

    function createUserInputLine() {
        // Remove welcome message on first interaction
        const welcome = document.querySelector('.welcome-message');
        if (welcome && interactionFlow.children.length > 1) {
             welcome.style.display = 'none';
        }

        const line = document.createElement('div');
        line.className = 'interaction-line user-input-line';

        const inputSpan = document.createElement('span');
        inputSpan.className = 'active-input';
        inputSpan.contentEditable = true;

        line.appendChild(inputSpan);
        interactionFlow.appendChild(line);
        inputSpan.focus();

        inputSpan.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const command = inputSpan.innerText.trim();
                if (command) {
                    executeCommand(command, inputSpan);
                }
            }
        });

        document.addEventListener('click', () => {
            if (!isStreaming) inputSpan.focus();
        });

        interactionFlow.scrollTop = interactionFlow.scrollHeight;
    }

    function executeCommand(command, inputSpan) {
        if (isStreaming) return;

        isStreaming = true;
        lastUserCommand = command;
        inputSpan.contentEditable = false;
        inputSpan.classList.remove('active-input');

        statusBar.innerText = "Processing...";

        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.handle_command(command);
        } else {
            setTimeout(() => {
                onAIStreamStart();
                onAIStreamChunk("Demo Mode: Backend not connected. Your command: " + command);
                onAIStreamEnd();
            }, 500);
        }
    }

    // Bridge Functions
    window.onAIStreamStart = () => {
        isStreaming = true;
        const thinkingStatus = document.getElementById('thinking-status');
        if (thinkingStatus) thinkingStatus.classList.add('active');

        currentAILine = document.createElement('div');
        currentAILine.className = 'interaction-line ai-output-line';
        interactionFlow.appendChild(currentAILine);
        interactionFlow.scrollTop = interactionFlow.scrollHeight;
    };

    window.onAIStreamChunk = (chunk) => {
        if (currentAILine) {
            // Check if chunk is a JSON object representing specialized content
            try {
                const data = JSON.parse(chunk);
                if (data.type === 'code_block') {
                    renderCodeBlock(data);
                    return;
                } else if (data.type === 'data_table') {
                    renderDataTable(data);
                    return;
                } else if (data.type === 'chart') {
                    renderChart(data);
                    return;
                }
            } catch (e) {
                // Not JSON, just append text
            }

            currentAILine.innerText += chunk;
            interactionFlow.scrollTop = interactionFlow.scrollHeight;
        }
    };

    function renderCodeBlock(data) {
        const block = document.createElement('div');
        block.className = 'code-block';

        const header = document.createElement('div');
        header.className = 'code-header';
        const langSpan = document.createElement('span');
        langSpan.textContent = data.language || 'code';
        const icon = document.createElement('i');
        icon.className = 'fas fa-terminal';
        header.appendChild(langSpan);
        header.appendChild(icon);

        const content = document.createElement('div');
        content.className = 'code-content';
        content.textContent = data.code;

        block.appendChild(header);
        block.appendChild(content);

        if (data.output) {
            const output = document.createElement('div');
            output.className = 'code-output';
            output.textContent = data.output;
            block.appendChild(output);
        }

        currentAILine.appendChild(block);
    }

    function renderDataTable(data) {
        const table = document.createElement('table');
        table.className = 'data-table';

        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        data.columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);

        const tbody = document.createElement('tbody');
        data.rows.forEach(rowData => {
            const tr = document.createElement('tr');
            rowData.forEach(cellData => {
                const td = document.createElement('td');
                td.textContent = cellData;
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

        table.appendChild(thead);
        table.appendChild(tbody);
        currentAILine.appendChild(table);
    }

    function renderChart(data) {
        const container = document.createElement('div');
        container.className = 'chart-container';
        const img = document.createElement('img');
        img.src = data.url;
        img.alt = "Chart";
        container.appendChild(img);
        currentAILine.appendChild(container);
    }

    window.openEditor = (content, filename) => {
        markdownEditor.value = content || "";
        document.getElementById('editor-filename').innerText = filename || "未命名文档";
        editorOverlay.classList.add('active');
    };

    window.onAIStreamEnd = () => {
        isStreaming = false;
        const thinkingStatus = document.getElementById('thinking-status');
        if (thinkingStatus) thinkingStatus.classList.remove('active');

        statusBar.innerText = "Ready";
        createUserInputLine();
    };

    window.onTerminalOutput = (data) => term.write(data);

    window.onVoiceStatusChange = (isListening) => {
        const dot = document.getElementById('voice-status');
        const voiceIcon = navVoice.querySelector('i');
        if (isListening) {
            dot.classList.add('active');
            voiceIcon.style.color = '#f44336';
        } else {
            dot.classList.remove('active');
            voiceIcon.style.color = 'inherit';
        }
    };

    window.onNostalgiaMode = () => {
        document.body.classList.add('nostalgia-mode');
        const msg = document.createElement('div');
        msg.className = 'nostalgia-overlay';
        msg.innerHTML = '<h1>怀旧模式：一中往事</h1><p>那年的早读，Butler 陪你补上。</p>';
        document.body.appendChild(msg);
        setTimeout(() => msg.classList.add('fade-out'), 3000);
        setTimeout(() => msg.remove(), 4000);
    };

    // Nav Events
    function setActiveNav(item) {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
    }

    navTerminal.addEventListener('click', () => {
        setActiveNav(navTerminal);
        terminalOverlay.classList.toggle('hidden');
        if (!terminalOverlay.classList.contains('hidden')) {
            fitAddon.fit();
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.start_terminal();
            }
        }
    });

    navVoice.addEventListener('click', () => {
        setActiveNav(navVoice);
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.handle_command("/voice-toggle");
        }
    });

    navHome.addEventListener('click', () => {
        setActiveNav(navHome);
        // Clear history and show welcome
        while (interactionFlow.firstChild) {
            interactionFlow.removeChild(interactionFlow.firstChild);
        }
        const welcome = document.createElement('div');
        welcome.className = 'welcome-message';
        const h1 = document.createElement('h1');
        h1.textContent = 'Butler';
        const p = document.createElement('p');
        p.textContent = 'How can I help you today?';
        welcome.appendChild(h1);
        welcome.appendChild(p);
        interactionFlow.appendChild(welcome);
        createUserInputLine();
    });

    navEditor.addEventListener('click', () => {
        setActiveNav(navEditor);
        editorOverlay.classList.toggle('active');
    });

    navSettings.addEventListener('click', () => {
        setActiveNav(navSettings);
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.handle_command("/profile");
        }
    });

    closeEditorBtn.addEventListener('click', () => {
        editorOverlay.classList.remove('active');
    });

    // Toolbar logic
    toolbarButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const action = btn.getAttribute('title');
            insertMarkdown(action);
        });
    });

    function insertMarkdown(action) {
        const start = markdownEditor.selectionStart;
        const end = markdownEditor.selectionEnd;
        const text = markdownEditor.value;
        const selectedText = text.substring(start, end);
        let before = text.substring(0, start);
        let after = text.substring(end);
        let newText = "";

        switch(action) {
            case '粗体':
                newText = `**${selectedText || '粗体文字'}**`;
                break;
            case '斜体':
                newText = `*${selectedText || '斜体文字'}*`;
                break;
            case '插入图片':
                newText = `![描述](url)`;
                break;
            case '插入表格':
                newText = `\n| Header | Header |\n| --- | --- |\n| Cell | Cell |\n`;
                break;
        }

        markdownEditor.value = before + newText + after;
        markdownEditor.focus();
        markdownEditor.setSelectionRange(start + newText.length, start + newText.length);
    }

    saveEditorBtn.addEventListener('click', () => {
        const content = markdownEditor.value;
        const filename = document.getElementById('editor-filename').innerText;
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.save_editor_content(content, filename).then(path => {
                statusBar.innerText = "Saved to " + path;
            });
        }
    });

    openOfficeBtn.addEventListener('click', () => {
        const filename = document.getElementById('editor-filename').innerText;
        // In a real app we'd get the full path. For demo, we assume it's in data/
        const dummyPath = "data/" + filename;
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.open_office(dummyPath);
        }
    });

    closeTerminalBtn.addEventListener('click', () => {
        terminalOverlay.classList.add('hidden');
    });

    // Start
    setTimeout(createUserInputLine, 1000);
});
