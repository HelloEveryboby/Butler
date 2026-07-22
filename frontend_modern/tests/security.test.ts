import { describe, it, expect } from 'vitest';
import {
  sanitizeCommand,
  isValidFilePath,
  isValidSkillName,
  isValidMethodName,
  checkRateLimit,
} from '@/utils/security';

describe('Security Utils', () => {
  describe('sanitizeCommand', () => {
    it('should accept normal commands', () => {
      expect(sanitizeCommand('hello world')).toBe('hello world');
      expect(sanitizeCommand('/doctor')).toBe('/doctor');
      expect(sanitizeCommand('  trim me  ')).toBe('trim me');
    });

    it('should reject empty input', () => {
      expect(sanitizeCommand('')).toBeNull();
      expect(sanitizeCommand('   ')).toBeNull();
    });

    it('should reject non-string input', () => {
      expect(sanitizeCommand(null as any)).toBeNull();
      expect(sanitizeCommand(undefined as any)).toBeNull();
      expect(sanitizeCommand(123 as any)).toBeNull();
    });

    it('should reject oversized input', () => {
      const long = 'a'.repeat(10001);
      expect(sanitizeCommand(long)).toBeNull();
    });

    it('should accept max length input', () => {
      const maxLen = 'a'.repeat(10000);
      expect(sanitizeCommand(maxLen)).toBe(maxLen);
    });

    it('should reject control characters', () => {
      expect(sanitizeCommand('hello\x00world')).toBeNull();
      expect(sanitizeCommand('hello\x08world')).toBeNull();
    });

    it('should allow newlines and tabs', () => {
      expect(sanitizeCommand('hello\nworld')).toBe('hello\nworld');
      expect(sanitizeCommand('hello\tworld')).toBe('hello\tworld');
    });
  });

  describe('isValidFilePath', () => {
    it('should accept normal paths', () => {
      expect(isValidFilePath('/home/user/file.txt')).toBe(true);
      expect(isValidFilePath('data/config.json')).toBe(true);
      expect(isValidFilePath('file.txt')).toBe(true);
    });

    it('should reject path traversal', () => {
      expect(isValidFilePath('../etc/passwd')).toBe(false);
      expect(isValidFilePath('foo/../../../etc')).toBe(false);
    });

    it('should reject special characters', () => {
      expect(isValidFilePath('file<script>.txt')).toBe(false);
      expect(isValidFilePath('file|pipe.txt')).toBe(false);
      expect(isValidFilePath('file?.txt')).toBe(false);
    });

    it('should reject empty input', () => {
      expect(isValidFilePath('')).toBe(false);
    });

    it('should reject sensitive directories', () => {
      expect(isValidFilePath('/etc/passwd')).toBe(false);
      expect(isValidFilePath('/proc/self/environ')).toBe(false);
    });
  });

  describe('isValidSkillName', () => {
    it('should accept valid names', () => {
      expect(isValidSkillName('my_skill')).toBe(true);
      expect(isValidSkillName('Skill123')).toBe(true);
      expect(isValidSkillName('_private')).toBe(true);
    });

    it('should reject invalid names', () => {
      expect(isValidSkillName('my-skill')).toBe(false); // hyphen
      expect(isValidSkillName('123skill')).toBe(false); // starts with number
      expect(isValidSkillName('my skill')).toBe(false); // space
      expect(isValidSkillName('')).toBe(false);
    });
  });

  describe('isValidMethodName', () => {
    it('should accept valid method names', () => {
      expect(isValidMethodName('list')).toBe(true);
      expect(isValidMethodName('get_data')).toBe(true);
    });

    it('should reject injection attempts', () => {
      expect(isValidMethodName('list; rm -rf /')).toBe(false);
      expect(isValidMethodName('list()')).toBe(false);
    });
  });

  describe('checkRateLimit', () => {
    it('should allow requests within limit', () => {
      // Reset by calling multiple times within limit
      for (let i = 0; i < 5; i++) {
        expect(checkRateLimit()).toBe(true);
      }
    });

    it('should block after limit exceeded', () => {
      // Exhaust the limit
      for (let i = 0; i < 5; i++) {
        checkRateLimit();
      }
      // 6th should be blocked
      expect(checkRateLimit()).toBe(false);
    });
  });
});
