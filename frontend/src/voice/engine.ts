/**
 * Type-Safe Web Audio Engine with Speech Recognition (STT), Synthesis (TTS), and Audio Analysis
 */

import { appConfig } from '../config';
import { PyWebViewBridge } from '../core/bridge';

export interface AudioFrequencyData {
  byteArray: Uint8Array;
  floatArray: Float32Array;
  averageVolume: number;
}

export class VoiceEngine {
  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private mediaStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private recognition: any = null;
  private isListening: boolean = false;
  private worker: Worker | null = null;
  private onDataCallbacks: Array<(data: AudioFrequencyData) => void> = [];
  private onResultCallbacks: Array<(transcript: string, isFinal: boolean) => void> = [];
  private onStateCallbacks: Array<(isListening: boolean) => void> = [];

  constructor() {
    this.initSpeechRecognition();
    this.initAudioWorker();
  }

  private initSpeechRecognition(): void {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      this.recognition = new SpeechRecognition();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = 'zh-CN';

      this.recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            final += transcript;
          } else {
            interim += transcript;
          }
        }

        const text = final || interim;
        if (text) {
          const isFinal = Boolean(final);
          this.onResultCallbacks.forEach((cb) => cb(text.trim(), isFinal));
        }
      };

      this.recognition.onerror = (err: any) => {
        console.warn('[VoiceEngine] Web Speech API error:', err);
      };

      this.recognition.onend = () => {
        if (this.isListening) {
          // Restart if continuous listening is desired
          try {
            this.recognition.start();
          } catch (e) {
            // ignore
          }
        }
      };
    } else {
      console.warn('[VoiceEngine] Web Speech API is not natively supported in this WebBrowser environment.');
    }
  }

  private initAudioWorker(): void {
    try {
      // Inlined Worker Blob for zero external Worker file dependency
      const workerCode = `
        self.onmessage = function(e) {
          const { type, buffer } = e.data;
          if (type === 'PROCESS_AUDIO') {
            let sum = 0;
            for (let i = 0; i < buffer.length; i++) {
              sum += Math.abs(buffer[i]);
            }
            const rms = Math.sqrt(sum / buffer.length);
            self.postMessage({ type: 'AUDIO_STATS', rms });
          }
        };
      `;
      const blob = new Blob([workerCode], { type: 'application/javascript' });
      this.worker = new Worker(URL.createObjectURL(blob));
      this.worker.onmessage = (e) => {
        if (e.data.type === 'AUDIO_STATS') {
          // Worker finished background processing
        }
      };
    } catch (e) {
      console.warn('[VoiceEngine] Failed to create background Audio Worker:', e);
    }
  }

  public async startListening(): Promise<boolean> {
    if (this.isListening) return true;

    try {
      // Initialize AudioContext on user interaction
      if (!this.audioCtx) {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        this.audioCtx = new AudioContextClass();
      }
      if (this.audioCtx.state === 'suspended') {
        await this.audioCtx.resume();
      }

      // Request microphone access for Audio Visualizer
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 256;
      this.analyser.smoothingTimeConstant = 0.8;

      this.sourceNode = this.audioCtx.createMediaStreamSource(this.mediaStream);
      this.sourceNode.connect(this.analyser);

      this.isListening = true;
      this.notifyState(true);

      // Start Web Speech API if supported, or fallback to Python voice service
      if (this.recognition) {
        try {
          this.recognition.start();
        } catch (e) {
          // Already running
        }
      } else if (PyWebViewBridge.isAvailable()) {
        PyWebViewBridge.handleCommand('/voice-toggle');
      }

      this.startAudioAnalysisLoop();
      return true;
    } catch (err) {
      console.error('[VoiceEngine] Failed to start microphone / Web Audio:', err);
      this.isListening = false;
      this.notifyState(false);

      // Fallback to PyWebView backend if browser mic denied/unsupported
      if (PyWebViewBridge.isAvailable()) {
        PyWebViewBridge.handleCommand('/voice-toggle');
      }
      return false;
    }
  }

  public stopListening(): void {
    if (!this.isListening) return;

    this.isListening = false;
    this.notifyState(false);

    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {
        // ignore
      }
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
  }

  private startAudioAnalysisLoop(): void {
    if (!this.analyser || !this.isListening) return;

    const bufferLength = this.analyser.frequencyBinCount;
    const byteArray = new Uint8Array(bufferLength);
    const floatArray = new Float32Array(bufferLength);

    const tick = () => {
      if (!this.isListening || !this.analyser) return;

      this.analyser.getByteFrequencyData(byteArray);
      this.analyser.getFloatTimeDomainData(floatArray);

      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += byteArray[i];
      }
      const averageVolume = sum / bufferLength;

      // Pass audio buffer to worker for heavy background analysis
      if (this.worker && floatArray.length > 0) {
        this.worker.postMessage({ type: 'PROCESS_AUDIO', buffer: floatArray }, [floatArray.buffer.slice(0)]);
      }

      const freqData: AudioFrequencyData = { byteArray, floatArray, averageVolume };
      this.onDataCallbacks.forEach((cb) => cb(freqData));

      requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }

  public speak(text: string): Promise<void> {
    return new Promise((resolve) => {
      if (!appConfig.get('ttsEnabled')) {
        resolve();
        return;
      }

      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'zh-CN';
        utterance.rate = appConfig.get('ttsRate');
        utterance.pitch = appConfig.get('ttsPitch');

        utterance.onend = () => resolve();
        utterance.onerror = () => resolve();

        window.speechSynthesis.speak(utterance);
      } else {
        resolve();
      }
    });
  }

  public onFrequencyData(callback: (data: AudioFrequencyData) => void): void {
    this.onDataCallbacks.push(callback);
  }

  public onSpeechResult(callback: (transcript: string, isFinal: boolean) => void): void {
    this.onResultCallbacks.push(callback);
  }

  public onStateChange(callback: (isListening: boolean) => void): void {
    this.onStateCallbacks.push(callback);
  }

  private notifyState(isListening: boolean): void {
    this.onStateCallbacks.forEach((cb) => cb(isListening));
    if (window.onVoiceStatusChange) {
      window.onVoiceStatusChange(isListening);
    }
  }

  public getListeningState(): boolean {
    return this.isListening;
  }
}

export const voiceEngine = new VoiceEngine();
