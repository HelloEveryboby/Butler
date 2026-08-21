/**
 * Butler Time Slit Editor: Code tearing animation and Monaco integration.
 */

class TimeSlitEditor {
  public activeSlit: HTMLElement | null = null;
  public editor: any = null;

  constructor() {
    this.init();
  }

  public init(): void {
    document.addEventListener('click', (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target) return;
      const text = target.innerText || '';
      const match = text.match(/File "([^"]+)", line (\d+)/) || text.match(/([a-zA-Z0-9_\-\/.]+\.py):(\d+)/);
      if (match) {
        const filePath = match[1];
        const line = parseInt(match[2], 10);
        const cardElement = target.closest('.interaction-line, .fix-card, .overlay-panel, .matrix-cell') as HTMLElement;
        if (cardElement) {
          this.openSlit(filePath, line, cardElement);
        }
      }
    });
  }

  public async openSlit(filePath: string, line: number, cardElement: HTMLElement): Promise<void> {
    if (this.activeSlit) this.closeSlit();

    window.stateMatrix?.update('editor.active', true);
    window.stateMatrix?.update('editor.filePath', filePath);

    cardElement.classList.add('slit-container');
    const content = cardElement.innerHTML;

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

    setTimeout(() => {
      const top = cardElement.querySelector('.slit-top') as HTMLElement;
      const bottom = cardElement.querySelector('.slit-bottom') as HTMLElement;
      const editorWin = cardElement.querySelector('.slit-editor-window') as HTMLElement;

      if (top && bottom && editorWin) {
        top.style.transform = 'translateY(-40%) rotateX(15deg)';
        bottom.style.transform = 'translateY(40%) rotateX(-15deg)';
        editorWin.style.opacity = '1';
        editorWin.style.transform = 'scale(1)';
        editorWin.style.zIndex = '20';
        editorWin.style.pointerEvents = 'auto';
      }
    }, 50);

    this.activeSlit = cardElement;

    if (window.monaco_ready || window.monaco) {
      this.initMonaco('monaco-slit-editor', filePath, line);
    } else {
      console.error('Monaco Editor not ready');
    }
  }

  public async initMonaco(containerId: string, filePath: string, line: number): Promise<void> {
    const container = document.getElementById(containerId);
    if (!container || !window.monaco) return;
    const content = await this.getFileContent(filePath);

    this.editor = window.monaco.editor.create(container, {
      value: content,
      language: filePath.endsWith('.py') ? 'python' : 'javascript',
      theme: 'vs-dark',
      automaticLayout: true,
      fontSize: 14,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      roundedSelection: true,
      cursorSmoothCaretAnimation: true,
    });

    this.editor.revealLineInCenter(line);
    this.editor.setSelection({
      startLineNumber: line,
      startColumn: 1,
      endLineNumber: line,
      endColumn: 1000,
    });

    this.editor.addCommand(window.monaco.KeyMod.CtrlCmd | window.monaco.KeyCode.KeyS, () => {
      this.saveAndClose(filePath);
    });

    this.editor.addCommand(window.monaco.KeyCode.Escape, () => {
      this.closeSlit();
    });
  }

  public async getFileContent(path: string): Promise<string> {
    if (window.pywebview && window.pywebview.api) {
      const res = await window.pywebview.api.get_file_base64(path);
      if (res && !(res as any).error) {
        try {
          const binaryString = atob(res);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          return new TextDecoder().decode(bytes);
        } catch (e) {
          return atob(res);
        }
      }
    }
    return '# 正在读取文件: ' + path + '\n# (如果这是 Mock 环境，将显示此消息)';
  }

  public async saveAndClose(path: string): Promise<void> {
    if (!this.editor || !this.activeSlit) return;
    const content = this.editor.getValue();
    if (window.pywebview && window.pywebview.api) {
      await window.pywebview.api.save_editor_content(content, path);
      console.log(`Saved: ${path}`);
    }

    const flash = document.createElement('div');
    flash.className = 'repair-flash';
    flash.style.cssText =
      'position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: white; opacity: 0; z-index: 100; pointer-events: none;';
    this.activeSlit.appendChild(flash);

    flash.animate([{ opacity: 0 }, { opacity: 0.8 }, { opacity: 0 }], {
      duration: 600,
      easing: 'ease-out',
    });

    setTimeout(() => this.closeSlit(), 400);
  }

  public closeSlit(): void {
    if (!this.activeSlit) return;

    const top = this.activeSlit.querySelector('.slit-top') as HTMLElement;
    const bottom = this.activeSlit.querySelector('.slit-bottom') as HTMLElement;
    const editorWin = this.activeSlit.querySelector('.slit-editor-window') as HTMLElement;

    if (top && bottom && editorWin) {
      top.style.transform = 'translateY(0) rotateX(0)';
      bottom.style.transform = 'translateY(0) rotateX(0)';
      editorWin.style.opacity = '0';
      editorWin.style.transform = 'scale(0.9)';
    }

    setTimeout(() => {
      if (this.activeSlit) {
        const topEl = this.activeSlit.querySelector('.slit-top');
        if (topEl) {
          const originalContent = topEl.innerHTML;
          this.activeSlit.innerHTML = originalContent;
        }
        this.activeSlit.classList.remove('slit-container');
        this.activeSlit = null;
      }
    }, 800);

    if (this.editor) {
      this.editor.dispose();
      this.editor = null;
    }
    window.stateMatrix?.update('editor.active', false);
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    window.timeSlitEditor = new TimeSlitEditor();
    (window as any).TimeSlitEditor = TimeSlitEditor;
  });
}
