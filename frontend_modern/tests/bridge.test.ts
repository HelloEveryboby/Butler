import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WebBridge } from '@/api/bridge-web';

describe('WebBridge', () => {
  let bridge: WebBridge;

  beforeEach(() => {
    bridge = new WebBridge();
    // Mock window callbacks
    (window as any).onAIStreamStart = vi.fn();
    (window as any).onAIStreamChunk = vi.fn();
    (window as any).onAIStreamEnd = vi.fn();
  });

  it('should implement ButlerBridge interface', () => {
    expect(typeof bridge.handleCommand).toBe('function');
    expect(typeof bridge.submitFlashCommand).toBe('function');
    expect(typeof bridge.hideFlash).toBe('function');
    expect(typeof bridge.callSkill).toBe('function');
    expect(typeof bridge.pauseOutput).toBe('function');
    expect(typeof bridge.openOffice).toBe('function');
    expect(typeof bridge.terminalInput).toBe('function');
  });

  it('should call stream callbacks on handleCommand', async () => {
    await bridge.handleCommand('test');

    expect((window as any).onAIStreamStart).toHaveBeenCalled();
    expect((window as any).onAIStreamChunk).toHaveBeenCalled();
    expect((window as any).onAIStreamEnd).toHaveBeenCalled();
  });

  it('should return mock data from callSkill', async () => {
    const result = await bridge.callSkill('workflow_engine', 'list');
    expect(result).toBeDefined();
    expect(typeof result).toBe('object');
  });

  it('should return empty object for unknown skill', async () => {
    const result = await bridge.callSkill('nonexistent', 'method');
    expect(result).toEqual({});
  });

  it('should not throw on any method call', () => {
    expect(() => bridge.pauseOutput()).not.toThrow();
    expect(() => bridge.terminalInput('test')).not.toThrow();
    expect(() => bridge.openOffice('/test/path')).not.toThrow();
  });
});
