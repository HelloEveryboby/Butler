document.addEventListener('DOMContentLoaded', () => {
    const interactionFlow = document.getElementById('interaction-flow');
    const terminalOverlay = document.getElementById('terminal-overlay');
    const closeTerminalBtn = document.getElementById('close-terminal');
    const statusBar = document.getElementById('status-bar');

    // Dock Items
    const dockTerminal = document.getElementById('dock-terminal');
    const dockVoice = document.getElementById('dock-voice');
    const dockPause = document.getElementById('dock-pause');
    const dockRetry = document.getElementById('dock-retry');
    const dockHome = document.getElementById('dock-home');

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
        statusBar.innerText = "Ready";
        createUserInputLine();
    };

    window.onTerminalOutput = (data) => term.write(data);

    window.onVoiceStatusChange = (isListening) => {
        const dot = document.getElementById('voice-status');
        const voiceIcon = dockVoice.querySelector('i');
        if (isListening) {
            dot.classList.add('listening');
            voiceIcon.style.color = '#ff3b30';
        } else {
            dot.classList.remove('listening');
            voiceIcon.style.color = 'white';
        }
    };

    // Dock Events
    dockTerminal.addEventListener('click', () => {
        terminalOverlay.classList.toggle('hidden');
        if (!terminalOverlay.classList.contains('hidden')) {
            fitAddon.fit();
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.start_terminal();
            }
        }
    });

    dockVoice.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api) {
            // Assume bridge has a way to toggle voice
            // For now we use the existing mechanism if available via jarvis panel command
            // or we might need to expose it to bridge
            window.pywebview.api.handle_command("/voice-toggle");
        }
    });

    dockPause.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.pause_output();
        }
    });

    dockRetry.addEventListener('click', () => {
        if (!isStreaming && lastUserCommand) {
            if (currentAILine) currentAILine.remove();
            const activeInput = document.querySelector('.active-input');
            if (activeInput) activeInput.parentElement.remove();

            const line = document.createElement('div');
            line.className = 'interaction-line user-input-line';
            const span = document.createElement('span');
            span.innerText = lastUserCommand;
            line.appendChild(span);
            interactionFlow.appendChild(line);

            executeCommand(lastUserCommand, span);
        }
    });

    dockHome.addEventListener('click', () => {
        // Clear history and show welcome
        interactionFlow.innerHTML = '';
        const welcome = document.createElement('div');
        welcome.className = 'welcome-message';
        welcome.innerHTML = '<h1>Butler</h1><p>How can I help you today?</p>';
        interactionFlow.appendChild(welcome);
        createUserInputLine();
    });

    closeTerminalBtn.addEventListener('click', () => {
        terminalOverlay.classList.add('hidden');
    });

    // Start
    setTimeout(createUserInputLine, 1000);
});
