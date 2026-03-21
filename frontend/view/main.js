document.addEventListener('DOMContentLoaded', () => {
    const interactionFlow = document.getElementById('interaction-flow');
    const terminalOverlay = document.getElementById('terminal-overlay');
    const closeTerminalBtn = document.getElementById('close-terminal');
    const statusBar = { innerText: "" };

    // Nav Bar Items (Google)
    const navHome = document.getElementById('nav-home');
    const navTerminal = document.getElementById('nav-terminal');
    const navVoice = document.getElementById('nav-voice');
    const navEditor = document.getElementById('nav-editor');
    const navSettings = document.getElementById('nav-settings');

    // Dock Items (Apple)
    const dockHome = document.getElementById('dock-home');
    const dockTerminal = document.getElementById('dock-terminal');
    const dockVoice = document.getElementById('dock-voice');
    const dockEditor = document.getElementById('dock-editor');
    const dockSettings = document.getElementById('dock-settings');
    const dockPause = document.getElementById('dock-pause');
    const dockRetry = document.getElementById('dock-retry');

    // Theme & Background Toggle
    const themeToggle = document.getElementById('theme-toggle');
    const bgUploadBtn = document.getElementById('bg-upload-btn');
    const bgUploadInput = document.getElementById('bg-upload');

    // Editor Components
    const editorOverlay = document.getElementById('editor-overlay');
    const closeEditorBtn = document.getElementById('close-editor');
    const markdownEditor = document.getElementById('markdown-editor');
    const saveEditorBtn = document.getElementById('save-editor');
    const openOfficeBtn = document.getElementById('open-in-office');

    let isStreaming = false;
    let currentAILine = null;
    let lastUserCommand = "";

    // Terminal initialization
    const term = new Terminal({
        cursorBlink: true,
        theme: { background: '#141414', foreground: '#f0f0f0' },
        fontSize: 14,
        fontFamily: 'SFMono-Regular, Consolas, monospace'
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
        const welcome = document.querySelector('.welcome-message');
        if (welcome && interactionFlow.children.length > 1) welcome.style.display = 'none';

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
                if (command) executeCommand(command, inputSpan);
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
            currentAILine.innerText += chunk;
            interactionFlow.scrollTop = interactionFlow.scrollHeight;
        }
    };

    window.onAIStreamEnd = () => {
        isStreaming = false;
        const thinkingStatus = document.getElementById('thinking-status');
        if (thinkingStatus) thinkingStatus.classList.remove('active');
        createUserInputLine();
    };

    window.onTerminalOutput = (data) => term.write(data);

    window.onVoiceStatusChange = (isListening) => {
        const dot = document.getElementById('voice-status');
        const voiceIconNav = navVoice.querySelector('i');
        const voiceIconDock = dockVoice.querySelector('i');
        if (isListening) {
            dot.classList.add('active');
            voiceIconNav.style.color = '#f44336';
            voiceIconDock.style.color = '#ff3b30';
        } else {
            dot.classList.remove('active');
            voiceIconNav.style.color = 'inherit';
            voiceIconDock.style.color = 'inherit';
        }
    };

    // Theme Logic
    themeToggle.addEventListener('click', () => {
        if (document.body.classList.contains('theme-google')) {
            document.body.classList.remove('theme-google');
            document.body.classList.add('theme-apple');
        } else {
            document.body.classList.remove('theme-apple');
            document.body.classList.add('theme-google');
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

    // Load saved background on startup
    const savedBg = localStorage.getItem('butler-custom-bg');
    if (savedBg) applyBackground(savedBg);

    // Navigation Events (Shared functions)
    const actions = {
        home: () => {
            while (interactionFlow.firstChild) interactionFlow.removeChild(interactionFlow.firstChild);
            const welcome = document.createElement('div');
            welcome.className = 'welcome-message';
            welcome.innerHTML = '<h1>Butler</h1><p>How can I help you today?</p>';
            interactionFlow.appendChild(welcome);
            createUserInputLine();
        },
        terminal: () => {
            terminalOverlay.classList.toggle('hidden');
            if (!terminalOverlay.classList.contains('hidden')) {
                fitAddon.fit();
                if (window.pywebview && window.pywebview.api) window.pywebview.api.start_terminal();
            }
        },
        voice: () => {
            if (window.pywebview && window.pywebview.api) window.pywebview.api.handle_command("/voice-toggle");
        },
        editor: () => editorOverlay.classList.toggle('active'),
        settings: () => {
            if (window.pywebview && window.pywebview.api) window.pywebview.api.handle_command("/profile");
        }
    };

    [navHome, dockHome].forEach(el => el.addEventListener('click', actions.home));
    [navTerminal, dockTerminal].forEach(el => el.addEventListener('click', actions.terminal));
    [navVoice, dockVoice].forEach(el => el.addEventListener('click', actions.voice));
    [navEditor, dockEditor].forEach(el => el.addEventListener('click', actions.editor));
    [navSettings, dockSettings].forEach(el => el.addEventListener('click', actions.settings));

    dockPause.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api) window.pywebview.api.pause_output();
    });

    dockRetry.addEventListener('click', () => {
        if (!isStreaming && lastUserCommand) {
            if (currentAILine) currentAILine.remove();
            const activeLine = document.querySelector('.user-input-line:last-child');
            if (activeLine) activeLine.remove();

            const line = document.createElement('div');
            line.className = 'interaction-line user-input-line';
            const span = document.createElement('span');
            span.innerText = lastUserCommand;
            line.appendChild(span);
            interactionFlow.appendChild(line);
            executeCommand(lastUserCommand, span);
        }
    });

    closeEditorBtn.addEventListener('click', () => editorOverlay.classList.remove('active'));
    closeTerminalBtn.addEventListener('click', () => terminalOverlay.classList.add('hidden'));

    // Start
    setTimeout(createUserInputLine, 1000);
});
