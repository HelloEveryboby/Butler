import { describe, it, expect, beforeEach } from 'vitest';
import { chatStore } from '@/stores/chat-store';

describe('ChatStore', () => {
  beforeEach(() => {
    chatStore.clear();
  });

  it('should start with empty state', () => {
    const state = chatStore.get();
    expect(state.messages).toEqual([]);
    expect(state.status).toBe('idle');
    expect(state.streamingContent).toBe('');
  });

  it('should add user message', () => {
    chatStore.addUserMessage('hello');
    const state = chatStore.get();
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0].role).toBe('user');
    expect(state.messages[0].content).toBe('hello');
  });

  it('should handle streaming lifecycle', () => {
    chatStore.startStream();
    expect(chatStore.get().status).toBe('streaming');

    chatStore.appendChunk('Hello ');
    chatStore.appendChunk('World');
    expect(chatStore.get().streamingContent).toBe('Hello World');

    chatStore.endStream();
    const state = chatStore.get();
    expect(state.status).toBe('idle');
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0].role).toBe('assistant');
    expect(state.messages[0].content).toBe('Hello World');
    expect(state.streamingContent).toBe('');
  });

  it('should not add empty stream as message', () => {
    chatStore.startStream();
    chatStore.endStream();
    expect(chatStore.get().messages).toHaveLength(0);
  });

  it('should set error status', () => {
    chatStore.setError('Something went wrong');
    const state = chatStore.get();
    expect(state.status).toBe('error');
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0].content).toContain('Something went wrong');
  });

  it('should notify listeners', () => {
    const listener = vi.fn();
    const unsub = chatStore.subscribe(listener);

    chatStore.addUserMessage('test');
    expect(listener).toHaveBeenCalled();

    unsub();
  });

  it('should clear all state', () => {
    chatStore.addUserMessage('msg1');
    chatStore.addUserMessage('msg2');
    chatStore.clear();

    const state = chatStore.get();
    expect(state.messages).toEqual([]);
    expect(state.status).toBe('idle');
  });
});
