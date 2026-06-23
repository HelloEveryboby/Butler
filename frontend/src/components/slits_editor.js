class TimeSlitEditor {
    constructor() {
        this.activeSlit = null;
        this.editor = null;
        this.init();
    }

    init() {
        // Intercept clicks on terminal error lines (mock for now)
        document.addEventListener('click', (e) => {
            const errorLine = e.target.closest('.xterm-rows > div');
            if (errorLine && errorLine.innerText.includes('File "')) {
                const match = errorLine.innerText.match(/File "([^"]+)", line (\d+)/);
                if (match) {
                    this.openSlit(match[1], parseInt(match[2]), e.target.closest('.overlay-panel'));
                }
            }
        });
    }

    async openSlit(filePath, line, cardElement) {
        if (this.activeSlit) this.closeSlit();

        // Visual "tearing" setup
        cardElement.classList.add('slit-container');

        // Clone the card content into two halves
        const content = cardElement.innerHTML;
        cardElement.innerHTML = `
            <div class="slit-halves-wrapper" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;">
                <div class="slit-top" style="position: absolute; top: 0; left: 0; width: 100%; height: 50%; overflow: hidden; background: inherit; border-bottom: 2px solid rgba(255,255,255,0.2); clip-path: polygon(0 0, 100% 0, 100% 100%, 80% 90%, 60% 100%, 40% 90%, 20% 100%, 0 90%);">
                    ${content}
                </div>
                <div class="slit-bottom" style="position: absolute; bottom: 0; left: 0; width: 100%; height: 50%; overflow: hidden; background: inherit; clip-path: polygon(0 10%, 20% 0, 40% 10%, 60% 0, 80% 10%, 100% 0, 100% 100%, 0 100%);">
                    <div style="transform: translateY(-50%)">${content}</div>
                </div>
            </div>
        `;

        const editorWindow = document.createElement('div');
        editorWindow.className = 'slit-editor-window';
        editorWindow.id = 'monaco-slit-editor';
        cardElement.appendChild(editorWindow);

        cardElement.classList.add('slit-open');
        this.activeSlit = cardElement;

        // Initialize Monaco (assuming it's loaded via script tag in index.html)
        if (window.monaco) {
            this.editor = monaco.editor.create(editorWindow, {
                value: await this.getFileContent(filePath),
                language: 'python',
                theme: 'vs-dark',
                automaticLayout: true
            });

            this.editor.revealLine(line);
            this.editor.setSelection({startLineNumber: line, startColumn: 1, endLineNumber: line, endColumn: 1000});

            this.editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
                this.saveAndClose(filePath);
            });
        }
    }

    async getFileContent(path) {
        if (window.pywebview && window.pywebview.api) {
            // Reusing bridge method or adding new one
            const res = await window.pywebview.api.get_file_base64(path);
            if (res && !res.error) {
                return atob(res);
            }
        }
        return "# Error loading file";
    }

    async saveAndClose(path) {
        const content = this.editor.getValue();
        if (window.pywebview && window.pywebview.api) {
            await window.pywebview.api.save_editor_content(content, path);
            // Trigger hot-reload in backend
            // window.pywebview.api.call_skill('skill_manager', 'reload', {skill_path: path});
        }

        // Closure animation
        this.activeSlit.classList.remove('slit-open');
        this.activeSlit.classList.add('slit-closing');

        // Visual "flash" of repair
        const flash = document.createElement('div');
        flash.className = 'repair-flash';
        this.activeSlit.appendChild(flash);

        setTimeout(() => {
            this.closeSlit();
        }, 600);
    }

    closeSlit() {
        if (!this.activeSlit) return;

        // Restore original content from one of the halves
        const topHalf = this.activeSlit.querySelector('.slit-top');
        if (topHalf) {
            const originalContent = topHalf.innerHTML;
            this.activeSlit.innerHTML = originalContent;
        }

        this.activeSlit.classList.remove('slit-container', 'slit-open', 'slit-closing');
        this.activeSlit = null;
        if (this.editor) {
            this.editor.dispose();
            this.editor = null;
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.timeSlitEditor = new TimeSlitEditor();
});
