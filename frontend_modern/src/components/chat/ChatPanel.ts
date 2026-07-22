/**
 * ChatPanel: 智能对话面板 (象限 0,0)
 *
 * 管理用户输入、AI 流式响应、消息历史、快捷指令等。
 */

import type { ButlerBridge } from '@/api/bridge';
import { escapeHTML } from '@/utils/escape';
import { toast } from '@/utils/toast';
import { stateMatrix } from '@/stores/state-matrix';

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
}

export class ChatPanel {
  private bridge: ButlerBridge;
  private messages: ChatMessage[] = [];
  private isStreaming = false;
  private streamBuffer = '';

  // DOM 元素引用
  private chatInput: HTMLElement | null = null;
  private chatMessages: HTMLElement | null = null;
  private sendBtn: HTMLElement | null = null;
  private welcomeMsg: HTMLElement | null = null;

  constructor(bridge: ButlerBridge) {
    this.bridge = bridge;
    this.init();
  }

  private init(): void {
    this.chatInput = document.getElementById('chat-input');
    this.chatMessages = document.getElementById('chat-messages');
    this.sendBtn = document.getElementById('send-command-btn');
    this.welcomeMsg = document.querySelector('.welcome-message');

    this.bindEvents();
    this.registerGlobalCallbacks();
  }

  private bindEvents(): void {
    if (this.chatInput) {
      this.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.send();
        }
      });
    }

    if (this.sendBtn) {
      this.sendBtn.addEventListener('click', () => this.send());
    }
  }

  /**
   * 注册 pywebview evaluate_js 全局回调
   * Python 后端通过这些函数推送 AI 流式响应
   */
  private registerGlobalCallbacks(): void {
    window.onAIStreamStart = () => {
      this.isStreaming = true;
      this.streamBuffer = '';
      this.showStreamingIndicator();
    };

    window.onAIStreamChunk = (chunk: string) => {
      if (!this.isStreaming) return;
      this.streamBuffer += chunk;
      this.updateStreamingContent(this.streamBuffer);
    };

    window.onAIStreamEnd = () => {
      this.isStreaming = false;
      if (this.streamBuffer) {
        this.addMessage('assistant', this.streamBuffer);
      }
      this.hideStreamingIndicator();
      this.streamBuffer = '';
    };
  }

  /**
   * 发送消息
   */
  async send(): Promise<void> {
    const input = this.chatInput;
    if (!input) return;

    const text = (input.innerText || input.textContent || '').trim();
    if (!text) return;

    // 隐藏欢迎消息
    if (this.welcomeMsg) {
      this.welcomeMsg.style.display = 'none';
    }

    // 添加用户消息
    this.addMessage('user', text);

    // 清空输入
    input.innerText = '';
    input.textContent = '';

    // 发送到后端
    await this.bridge.handleCommand(text);
  }

  /**
   * 添加消息到列表
   */
  private addMessage(role: ChatMessage['role'], content: string): void {
    const message: ChatMessage = {
      role,
      content,
      timestamp: Date.now(),
    };
    this.messages.push(message);
    this.renderMessage(message);
  }

  /**
   * 渲染单条消息
   */
  private renderMessage(message: ChatMessage): void {
    if (!this.chatMessages) return;

    const div = document.createElement('div');
    div.className = `chat-message message-${message.role}`;
    div.innerHTML = `
      <div class="message-avatar">${message.role === 'user' ? '👤' : '🤖'}</div>
      <div class="message-content">${escapeHTML(message.content)}</div>
    `;
    this.chatMessages.appendChild(div);
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
  }

  private showStreamingIndicator(): void {
    if (!this.chatMessages) return;
    const indicator = document.createElement('div');
    indicator.id = 'streaming-indicator';
    indicator.className = 'chat-message message-assistant streaming';
    indicator.innerHTML = `
      <div class="message-avatar">🤖</div>
      <div class="message-content"><span class="animate-pulse">思考中...</span></div>
    `;
    this.chatMessages.appendChild(indicator);
  }

  private updateStreamingContent(content: string): void {
    const indicator = document.getElementById('streaming-indicator');
    if (!indicator) return;
    const contentEl = indicator.querySelector('.message-content');
    if (contentEl) {
      contentEl.textContent = content;
    }
    // 滚动到底部
    if (this.chatMessages) {
      this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
  }

  private hideStreamingIndicator(): void {
    const indicator = document.getElementById('streaming-indicator');
    if (indicator) {
      indicator.remove();
    }
  }

  /**
   * 获取消息历史
   */
  getHistory(): ReadonlyArray<ChatMessage> {
    return this.messages;
  }

  /**
   * 清空消息
   */
  clear(): void {
    this.messages = [];
    if (this.chatMessages) {
      this.chatMessages.innerHTML = '';
    }
    if (this.welcomeMsg) {
      this.welcomeMsg.style.display = '';
    }
  }
}
