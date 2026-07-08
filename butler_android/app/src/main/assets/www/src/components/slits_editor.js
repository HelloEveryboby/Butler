class TimeSlitEditor {
    constructor() {
        this.activeSlit = null;
        this.editor = null;
        this.init();
    }

    init() {
        // Intercept clicks on terminal error lines or logs in UI
        document.addEventListener('click', (e) => {
            const text = e.target.innerText || "";
            // Regex to match file paths and line numbers
            const match = text.match(/File "([^"]+)", line (\d+)/) || text.match(/([a-zA-Z0-9_\-\/.]+\.py):(\d+)/);
            if (match) {
                const filePath = match[1];
                const line = parseInt(match[2]);
                const cardElement = e.target.closest('.interaction-line, .fix-card, .overlay-panel, .matrix-cell');
                if (cardElement) {
                    this.openSlit(filePath, line, cardElement);
                }
            }
        });
    }

    async openSlit(filePath, line, cardElement) {
        if (this.activeSlit) this.closeSlit();

        // 1. Centralized State Update
        window.stateMatrix.update('editor.active', true);
        window.stateMatrix.update('editor.filePath', filePath);

        // 2. Visual "tearing" animation
        cardElement.classList.add('slit-container');
        const content = cardElement.innerHTML;

        // Prepare the split view
        cardElement.innerHTML = `
            <div class="slit-halves-wrapper" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 10;">
                <div class="slit-top glass-surface" style="position: absolute; top: 0; left: 0; width: 100%; height: 50%; overflow: hidden; border-bottom: 1px solid rgba(255,255,255,0.3); clip-path: polygon(0 0, 100% 0, 100% 100%, 80% 90%, 60% 100%, 40% 90%, 20% 100%, 0 90%); transition: transform 0.8s var(--apple-easing);">
                    ${content}
                </div>
                <div class="slit-bottom glass-surface" style="position: absolute; bottom: 0; left: 0; width: 100%; height: 50%; overflow: hidden; clip-path: polygon(0 10%, 20% 0, 40% 10%, 60% 0, 80% 10%, 100% 0, 100% 100%, 0 100%); transition: transform 0.8s var(--apple-easing);">
                    <div style="transform: translateY(-50%)">${content}</div>
                </div>
            </div>
            <div class="slit-editor-window" id="monaco-slit-editor" style="position: absolute; top: 10%; left: 5%; width: 90%; height: 80%; opacity: 0; transform: scale(0.9); transition: all 0.6s var(--apple-easing); z-index: 5; background: #1e1e1e; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); overflow: hidden;"></div>
        `;

        // 3. Trigger Physics/Animation after a short delay
        setTimeout(() => {
            const top = cardElement.querySelector('.slit-top');
            const bottom = cardElement.querySelector('.slit-bottom');
            const editorWin = cardElement.querySelector('.slit-editor-window');

            top.style.transform = "translateY(-40%) rotateX(15deg)";
            bottom.style.transform = "translateY(40%) rotateX(-15deg)";
            editorWin.style.opacity = "1";
            editorWin.style.transform = "scale(1)";
            editorWin.style.zIndex = "20";
            editorWin.style.pointerEvents = "auto";
        }, 50);

        this.activeSlit = cardElement;

        // 4. Initialize Monaco
        if (window.monaco_ready || window.monaco) {
            this.initMonaco('monaco-slit-editor', filePath, line);
        } else {
            console.error("Monaco Editor not ready");
        }
    }

    async initMonaco(containerId, filePath, line) {
        const container = document.getElementById(containerId);
        const content = await this.getFileContent(filePath);

        this.editor = monaco.editor.create(container, {
            value: content,
            language: filePath.endsWith('.py') ? 'python' : 'javascript',
            theme: 'vs-dark',
            automaticLayout: true,
            fontSize: 14,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            roundedSelection: true,
            cursorSmoothCaretAnimation: true
        });

        this.editor.revealLineInCenter(line);
        this.editor.setSelection({
            startLineNumber: line,
            startColumn: 1,
            endLineNumber: line,
            endColumn: 1000
        });

        // Save on Ctrl+S
        this.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
            this.saveAndClose(filePath);
        });

        // Close on Escape
        this.editor.addCommand(monaco.KeyCode.Escape, () => {
            this.closeSlit();
        });
    }

    async getFileContent(path) {
        if (window.pywebview && window.pywebview.api) {
            const res = await window.pywebview.api.get_file_base64(path);
            if (res && !res.error) {
                try {
                    // Safe UTF-8 decode
                    const binaryString = atob(res);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    return new TextDecoder().decode(bytes);
                } catch(e) {
                    return atob(res);
                }
            }
        }
        return "# 正在读取文件: " + path + "\n# (如果这是 Mock 环境，将显示此消息)";
    }

    async saveAndClose(path) {
        const content = this.editor.getValue();
        if (window.pywebview && window.pywebview.api) {
            await window.pywebview.api.save_editor_content(content, path);
            console.log(`Saved: ${path}`);
        }

        // Repair Flash Animation
        const flash = document.createElement('div');
        flash.className = 'repair-flash';
        flash.style.cssText = "position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: white; opacity: 0; z-index: 100; pointer-events: none;";
        this.activeSlit.appendChild(flash);

        flash.animate([
            { opacity: 0 }, { opacity: 0.8 }, { opacity: 0 }
        ], { duration: 600, easing: 'ease-out' });

        setTimeout(() => this.closeSlit(), 400);
    }

    closeSlit() {
        if (!this.activeSlit) return;

        const top = this.activeSlit.querySelector('.slit-top');
        const bottom = this.activeSlit.querySelector('.slit-bottom');
        const editorWin = this.activeSlit.querySelector('.slit-editor-window');

        if (top && bottom && editorWin) {
            top.style.transform = "translateY(0) rotateX(0)";
            bottom.style.transform = "translateY(0) rotateX(0)";
            editorWin.style.opacity = "0";
            editorWin.style.transform = "scale(0.9)";
        }

        setTimeout(() => {
            if (this.activeSlit) {
                // Restore original state
                const originalContent = this.activeSlit.querySelector('.slit-top').innerHTML;
                this.activeSlit.innerHTML = originalContent;
                this.activeSlit.classList.remove('slit-container');
                this.activeSlit = null;
            }
        }, 800);

        if (this.editor) {
            this.editor.dispose();
            this.editor = null;
        }
        window.stateMatrix.update('editor.active', false);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.timeSlitEditor = new TimeSlitEditor();
});
