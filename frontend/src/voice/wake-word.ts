/**
 * Wake Word Detection & Voice Command Pattern Matcher
 */

import { appConfig } from '../config';
import { bhlClient } from '../ws/bhl-client';
import { voiceEngine } from './engine';

export class WakeWordDetector {
  private wakeWords: string[] = [];
  private onWakeWordCallbacks: Array<(wakeWord: string) => void> = [];
  private onCommandMatchedCallbacks: Array<(cmd: string, originalText: string) => void> = [];

  constructor() {
    this.refreshConfig();
    this.bindVoiceEngine();
  }

  public refreshConfig(): void {
    this.wakeWords = appConfig.get('wakeWords').map((w) => w.toLowerCase().trim());
  }

  private bindVoiceEngine(): void {
    voiceEngine.onSpeechResult((transcript: string, isFinal: boolean) => {
      this.processTranscript(transcript, isFinal);
    });
  }

  public processTranscript(transcript: string, isFinal: boolean): void {
    const cleanText = transcript.toLowerCase().trim();
    if (!cleanText) return;

    // 1. Check for wake words
    for (const wakeWord of this.wakeWords) {
      if (cleanText.includes(wakeWord)) {
        console.log(`[WakeWord] Detected wake word: "${wakeWord}" in "${cleanText}"`);
        this.notifyWakeWord(wakeWord);

        // Strip wake word from prompt
        const remaining = cleanText.replace(wakeWord, '').trim();
        if (remaining) {
          this.matchAndExecuteCommand(remaining);
        }
        return;
      }
    }

    // 2. If it's a final transcript, perform direct pattern matching
    if (isFinal) {
      this.matchAndExecuteCommand(cleanText);
    }
  }

  public matchAndExecuteCommand(text: string): boolean {
    const patterns = appConfig.get('commandPatterns');

    for (const { pattern, command } of patterns) {
      const regex = new RegExp(pattern, 'i');
      const match = regex.exec(text);

      if (match) {
        let finalCmd = command;
        for (let i = 1; i < match.length; i++) {
          finalCmd = finalCmd.replace(`$${i}`, match[i] || '');
        }
        finalCmd = finalCmd.trim();

        console.log(`[WakeWord] Pattern matched: "${text}" -> "${finalCmd}"`);
        this.notifyCommandMatched(finalCmd, text);
        bhlClient.sendCommand(finalCmd, {}, 'voice');
        return true;
      }
    }

    // Default fallback: send plain text as flash input command
    console.log(`[WakeWord] Submitting raw text command: "${text}"`);
    this.notifyCommandMatched(text, text);
    bhlClient.sendCommand(text, {}, 'voice');
    return true;
  }

  public onWakeWord(callback: (wakeWord: string) => void): void {
    this.onWakeWordCallbacks.push(callback);
  }

  public onCommandMatched(callback: (cmd: string, originalText: string) => void): void {
    this.onCommandMatchedCallbacks.push(callback);
  }

  private notifyWakeWord(wakeWord: string): void {
    this.onWakeWordCallbacks.forEach((cb) => cb(wakeWord));
    if (window.onWakeWordDetected) {
      window.onWakeWordDetected(wakeWord);
    }
  }

  private notifyCommandMatched(cmd: string, originalText: string): void {
    this.onCommandMatchedCallbacks.forEach((cb) => cb(cmd, originalText));
    if (window.onVoiceCommandRecognized) {
      window.onVoiceCommandRecognized(cmd);
    }
  }
}

export const wakeWordDetector = new WakeWordDetector();
