import { describe, it, expect, vi, beforeEach } from 'vitest';
import { escapeHTML, unescapeHTML } from '@/utils/escape';

describe('escapeHTML', () => {
  it('should escape ampersand', () => {
    expect(escapeHTML('a&b')).toBe('a&amp;b');
  });

  it('should escape angle brackets', () => {
    expect(escapeHTML('<script>alert(1)</script>')).toBe(
      '&lt;script&gt;alert(1)&lt;/script&gt;',
    );
  });

  it('should escape quotes', () => {
    expect(escapeHTML('"hello"')).toBe('&quot;hello&quot;');
    expect(escapeHTML("'hello'")).toBe('&#039;hello&#039;');
  });

  it('should handle null and undefined', () => {
    expect(escapeHTML(null)).toBe('');
    expect(escapeHTML(undefined)).toBe('');
  });

  it('should handle empty string', () => {
    expect(escapeHTML('')).toBe('');
  });

  it('should convert numbers to string', () => {
    expect(escapeHTML(123 as any)).toBe('123');
  });

  it('should escape multiple special chars', () => {
    expect(escapeHTML('<a href="x">')).toBe('&lt;a href=&quot;x&quot;&gt;');
  });

  it('should not escape safe content', () => {
    expect(escapeHTML('hello world 123')).toBe('hello world 123');
  });
});

describe('unescapeHTML', () => {
  it('should reverse escapeHTML', () => {
    const original = '<div class="test">Hello & World</div>';
    const escaped = escapeHTML(original);
    const unescaped = unescapeHTML(escaped);
    expect(unescaped).toBe(original);
  });

  it('should unescape all entities', () => {
    expect(unescapeHTML('&amp;')).toBe('&');
    expect(unescapeHTML('&lt;')).toBe('<');
    expect(unescapeHTML('&gt;')).toBe('>');
    expect(unescapeHTML('&quot;')).toBe('"');
    expect(unescapeHTML('&#039;')).toBe("'");
  });
});

describe('Toast (DOM-based)', () => {
  it('should create toast container on first call', async () => {
    // Dynamic import to avoid side effects at module load
    const { toast } = await import('@/utils/toast');
    toast.info('Test', 'Hello');

    const container = document.querySelector('.toast-container');
    expect(container).toBeTruthy();
  });

  it('should use textContent (no innerHTML)', async () => {
    const { toast } = await import('@/utils/toast');
    toast.info('XSS Test', '<img src=x onerror=alert(1)>');

    const msg = document.querySelector('.toast-message');
    expect(msg?.innerHTML).not.toContain('<img');
    expect(msg?.textContent).toBe('<img src=x onerror=alert(1)>');
  });
});
