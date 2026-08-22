/**
 * Type-Safe Liquid Ring Audio Spectrum Canvas Visualizer
 */

import { AudioFrequencyData, voiceEngine } from '../voice/engine';
import { appConfig } from '../config';

export class RingVisualizer {
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private isAnimating: boolean = false;
  private currentVol: number = 0;
  private animFrameId: number | null = null;

  constructor(canvasElement?: HTMLCanvasElement) {
    if (canvasElement) {
      this.attachCanvas(canvasElement);
    }
    this.bindAudio();
  }

  public attachCanvas(canvas: HTMLCanvasElement): void {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());
  }

  private resizeCanvas(): void {
    if (!this.canvas) return;
    const parent = this.canvas.parentElement;
    if (parent) {
      const rect = parent.getBoundingClientRect();
      this.canvas.width = rect.width || 300;
      this.canvas.height = rect.height || 300;
    }
  }

  private bindAudio(): void {
    voiceEngine.onFrequencyData((data: AudioFrequencyData) => {
      this.currentVol = data.averageVolume;
      if (this.canvas && this.ctx && !this.isAnimating) {
        this.renderFrame(data);
      }
    });

    voiceEngine.onStateChange((isListening) => {
      if (isListening) {
        this.startAnimation();
      } else {
        this.stopAnimation();
      }
    });
  }

  public startAnimation(): void {
    this.isAnimating = true;
    this.loop();
  }

  public stopAnimation(): void {
    this.isAnimating = false;
    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    this.clear();
  }

  private clear(): void {
    if (this.canvas && this.ctx) {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
  }

  private loop = (): void => {
    if (!this.isAnimating) return;
    this.animFrameId = requestAnimationFrame(this.loop);
  };

  public renderFrame(data: AudioFrequencyData): void {
    if (!this.canvas || !this.ctx) return;

    const width = this.canvas.width;
    const height = this.canvas.height;
    const centerX = width / 2;
    const centerY = height / 2;
    const baseRadius = appConfig.get('ringRadius') || 60;
    const byteArray = data.byteArray;
    const barsCount = Math.min(byteArray.length, 64);

    this.ctx.clearRect(0, 0, width, height);

    // Dynamic glow theme colors
    const theme = appConfig.get('audioVisualizerTheme');
    let mainColor = '0, 122, 255'; // Apple Blue
    let accentColor = '52, 199, 89'; // Apple Green

    if (theme === 'neon_cyan') {
      mainColor = '0, 240, 255';
      accentColor = '255, 0, 128';
    } else if (theme === 'liquid_purple') {
      mainColor = '175, 82, 222';
      accentColor = '255, 45, 85';
    } else if (theme === 'matrix_green') {
      mainColor = '48, 209, 88';
      accentColor = '50, 215, 75';
    }

    // Outer pulsing ambient aura ring
    const pulseVol = Math.min(1, this.currentVol / 128);
    const pulseRadius = baseRadius + pulseVol * 25;

    const auraGradient = this.ctx.createRadialGradient(centerX, centerY, baseRadius * 0.5, centerX, centerY, pulseRadius * 1.5);
    auraGradient.addColorStop(0, `rgba(${mainColor}, 0.3)`);
    auraGradient.addColorStop(0.7, `rgba(${accentColor}, 0.15)`);
    auraGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

    this.ctx.fillStyle = auraGradient;
    this.ctx.beginPath();
    this.ctx.arc(centerX, centerY, pulseRadius * 1.5, 0, Math.PI * 2);
    this.ctx.fill();

    // Inner Core Orb
    this.ctx.beginPath();
    this.ctx.arc(centerX, centerY, baseRadius * 0.8, 0, Math.PI * 2);
    this.ctx.fillStyle = `rgba(${mainColor}, 0.85)`;
    this.ctx.shadowBlur = 20;
    this.ctx.shadowColor = `rgba(${mainColor}, 0.9)`;
    this.ctx.fill();
    this.ctx.shadowBlur = 0;

    // Spectrum Bars arranged in a Circle
    const step = (Math.PI * 2) / barsCount;

    for (let i = 0; i < barsCount; i++) {
      const val = byteArray[i] || 0;
      const barHeight = (val / 255) * 45;
      const angle = i * step;

      const x1 = centerX + Math.cos(angle) * baseRadius;
      const y1 = centerY + Math.sin(angle) * baseRadius;
      const x2 = centerX + Math.cos(angle) * (baseRadius + barHeight + 4);
      const y2 = centerY + Math.sin(angle) * (baseRadius + barHeight + 4);

      this.ctx.beginPath();
      this.ctx.moveTo(x1, y1);
      this.ctx.lineTo(x2, y2);
      this.ctx.lineWidth = 3;
      this.ctx.strokeStyle = `rgba(${mainColor}, ${0.4 + (val / 255) * 0.6})`;
      this.ctx.lineCap = 'round';
      this.ctx.stroke();
    }
  }
}

export const ringVisualizer = new RingVisualizer();
