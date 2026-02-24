document.addEventListener('DOMContentLoaded', () => {
    const interactionFlow = document.getElementById('interaction-flow');
    const pauseBtn = document.getElementById('pause-btn');
    const retryBtn = document.getElementById('retry-btn');
    const terminalBtn = document.getElementById('terminal-btn');
    const terminalOverlay = document.getElementById('terminal-overlay');
    const closeTerminalBtn = document.getElementById('close-terminal');
    const statusBar = document.getElementById('status-bar');

    let isStreaming = false;
    let currentAILine = null;
    let lastUserCommand = "";

    // Terminal initialization
    const term = new Terminal({
        cursorBlink: true,
        theme: {
            background: '#1e1e1e'
        },
        fontSize: 14,
        fontFamily: 'Consolas, "Courier New", monospace'
    });
    const fitAddon = new (function() {
        this.fit = function() {
            const container = document.getElementById('terminal-container');
            const width = container.clientWidth;
            const height = container.clientHeight;
            const charWidth = 9; // Approximate
            const charHeight = 17; // Approximate
            const cols = Math.floor(width / charWidth);
            const rows = Math.floor(height / charHeight);
            term.resize(cols, rows);
        };
    })();

    term.open(document.getElementById('terminal-container'));
    fitAddon.fit();

    window.addEventListener('resize', () => {
        fitAddon.fit();
    });

    // Handle terminal input
    term.onData(data => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.terminal_input(data);
        }
    });

    // Function to create a new user input line
    function createUserInputLine() {
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

        // Ensure focus
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

        statusBar.innerText = "处理中...";

        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.handle_command(command);
        } else {
            // Demo mode
            setTimeout(() => {
                onAIStreamStart();
                onAIStreamChunk("这是一个演示响应。由于未检测到后端，我将模拟输出内容...");
                onAIStreamEnd();
            }, 500);
        }
    }

    // Bridge Functions (called from Python)
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
        statusBar.innerText = "就绪";
        createUserInputLine();
    };

    window.onTerminalOutput = (data) => {
        term.write(data);
    };

    window.onVoiceStatusChange = (isListening) => {
        const dot = document.getElementById('voice-status');
        if (isListening) {
            dot.classList.add('listening');
        } else {
            dot.classList.remove('listening');
        }
    };

    // UI Event Listeners
    pauseBtn.addEventListener('click', () => {
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.pause_output();
        }
    });

    retryBtn.addEventListener('click', () => {
        if (!isStreaming && lastUserCommand) {
            // Remove last AI output if exists
            if (currentAILine) currentAILine.remove();
            // We need to re-execute. Since createUserInputLine was called, we might have an empty active input.
            const activeInput = document.querySelector('.active-input');
            if (activeInput) {
                activeInput.parentElement.remove();
            }
            // Add a new user line but with the old command to show it's being retried
            const line = document.createElement('div');
            line.className = 'interaction-line user-input-line';
            const span = document.createElement('span');
            span.innerText = lastUserCommand;
            line.appendChild(span);
            interactionFlow.appendChild(line);

            executeCommand(lastUserCommand, span);
        }
    });

    terminalBtn.addEventListener('click', () => {
        terminalOverlay.classList.remove('hidden');
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.start_terminal();
        }
    });

    closeTerminalBtn.addEventListener('click', () => {
        terminalOverlay.classList.add('hidden');
    });

    // Start
    setTimeout(createUserInputLine, 1000);
});
