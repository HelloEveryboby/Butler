/**
 * 对话状态管理
 *
 * 管理 Chat 面板的消息列表、流式响应状态。
 */

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
}

export type ChatStatus = 'idle' | 'streaming' | 'error';

type Listener = (state: ChatState) => void;

export interface ChatState {
  messages: ChatMessage[];
  status: ChatStatus;
  streamingContent: string;
}

class ChatStore {
  private state: ChatState = {
    messages: [],
    status: 'idle',
    streamingContent: '',
  };

  private listeners = new Set<Listener>();

  get(): Readonly<ChatState> {
    return this.state;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /** AI 开始响应 */
  startStream(): void {
    this.state = { ...this.state, status: 'streaming', streamingContent: '' };
    this.notify();
  }

  /** 追加流式文本 */
  appendChunk(chunk: string): void {
    this.state = {
      ...this.state,
      streamingContent: this.state.streamingContent + chunk,
    };
    this.notify();
  }

  /** AI 响应结束 */
  endStream(): void {
    const content = this.state.streamingContent;
    if (content) {
      this.state = {
        ...this.state,
        messages: [
          ...this.state.messages,
          { role: 'assistant', content, timestamp: Date.now() },
        ],
        status: 'idle',
        streamingContent: '',
      };
    } else {
      this.state = { ...this.state, status: 'idle', streamingContent: '' };
    }
    this.notify();
  }

  /** 添加用户消息 */
  addUserMessage(content: string): void {
    this.state = {
      ...this.state,
      messages: [...this.state.messages, { role: 'user', content, timestamp: Date.now() }],
    };
    this.notify();
  }

  /** 设置错误状态 */
  setError(message: string): void {
    this.state = {
      ...this.state,
      status: 'error',
      messages: [...this.state.messages, { role: 'system', content: `❌ ${message}`, timestamp: Date.now() }],
    };
    this.notify();
  }

  /** 清空消息 */
  clear(): void {
    this.state = { messages: [], status: 'idle', streamingContent: '' };
    this.notify();
  }

  private notify(): void {
    for (const cb of this.listeners) {
      try {
        cb(this.state);
      } catch (err) {
        console.error('[ChatStore] listener error:', err);
      }
    }
  }
}

export const chatStore = new ChatStore();
