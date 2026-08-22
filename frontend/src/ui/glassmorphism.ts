/**
 * Glassmorphic UI Controller & DOM Event Binds
 */

import { voiceEngine } from '../voice/engine';
import { ringVisualizer } from '../canvas/ring-visualizer';
import { bhlClient } from '../ws/bhl-client';
import { PyWebViewBridge } from '../core/bridge';

export class GlassUIController {
  private micBtn: HTMLElement | null = null;
  private inputEl: HTMLInputElement | null = null;
  private canvasEl: HTMLCanvasElement | null = null;
  private statusBadge: HTMLElement | null = null;

  constructor() {
    this.initDOM();
  }

  public initDOM(): void {
    if (typeof document === 'undefined') return;

    this.micBtn = document.getElementById('mic-toggle');
    this.inputEl = document.getElementById('main-input') as HTMLInputElement;
    this.canvasEl = document.getElementById('voice-canvas') as HTMLCanvasElement;
    this.statusBadge = document.getElementById('voice-status');

    this.bindEvents();
    this.bindVoiceEngineState();
  }

  private bindEvents(): void {
    if (this.micBtn) {
      this.micBtn.addEventListener('click', () => {
        this.toggleVoice();
      });
    }

    if (this.inputEl) {
      this.inputEl.addEventListener('keydown', (e: KeyboardEvent) => {
        if (e.key === 'Enter') {
          const val = this.inputEl!.value.trim();
          if (val) {
            bhlClient.sendCommand(val, {}, 'flash_input');
            this.inputEl!.value = '';
          }
        } else if (e.key === 'Escape') {
          PyWebViewBridge.hideFlash();
        }
      });
    }

    if (this.canvasEl) {
      ringVisualizer.attachCanvas(this.canvasEl);
    }
  }

  private bindVoiceEngineState(): void {
    voiceEngine.onStateChange((isListening) => {
      this.updateMicUI(isListening);
    });

    voiceEngine.onSpeechResult((transcript: string, isFinal: boolean) => {
      if (this.inputEl && transcript) {
        this.inputEl.value = transcript;
        if (isFinal) {
          this.updateStatusBadge('已识别', 'success');
        } else {
          this.updateStatusBadge('正在聆听...', 'info');
        }
      }
    });
  }

  public toggleVoice(): void {
    const isListening = voiceEngine.getListeningState();
    if (isListening) {
      voiceEngine.stopListening();
    } else {
      voiceEngine.startListening();
    }
  }

  public updateMicUI(isListening: boolean): void {
    if (this.micBtn) {
      if (isListening) {
        this.micBtn.classList.add('active');
        this.micBtn.innerHTML = '<i class="fas fa-stop"></i>';
      } else {
        this.micBtn.classList.remove('active');
        this.micBtn.innerHTML = '<i class="fas fa-microphone"></i>';
      }
    }

    if (isListening) {
      this.updateStatusBadge('语音监听中', 'info');
    } else {
      this.updateStatusBadge('就绪', 'ready');
    }
  }

  public updateStatusBadge(text: string, type: 'info' | 'success' | 'ready' | 'error' = 'info'): void {
    if (!this.statusBadge) return;
    this.statusBadge.textContent = text;
  }
}

export const glassUI = new GlassUIController();
