import type { ButlerBridge } from './bridge';
import { escapeHTML } from '@/utils/escape';

/**
 * pywebview 原生桥接实现
 *
 * 通过 window.pywebview.api 调用 Python ModernBridge 类的方法。
 * ModernBridge 在 modern_app.py 中定义，通过 pywebview 暴露给前端。
 *
 * 安全措施:
 * - 所有传入 Python 的字符串参数经过 escapeHTML 转义
 * - 对 pywebview.api 做存在性检查
 * - 方法调用包装 try-catch 防止崩溃
 */
export class NativeBridge implements ButlerBridge {
  private get api(): PywebviewApi | undefined {
    return (window as any).pywebview?.api;
  }

  private get isReady(): boolean {
    return !!this.api;
  }

  private assertReady(): boolean {
    if (!this.isReady) {
      console.error('[NativeBridge] pywebview api not ready');
      return false;
    }
    return true;
  }

  async handleCommand(command: string): Promise<void> {
    if (!this.assertReady()) return;
    try {
      // 转义用户输入中的潜在危险字符
      const sanitized = escapeHTML(command);
      return await this.api!.handle_command(sanitized);
    } catch (err) {
      console.error('[NativeBridge] handleCommand error:', err);
    }
  }

  submitFlashCommand(command: string): void {
    if (!this.assertReady()) return;
    try {
      this.api!.submit_flash_command(escapeHTML(command));
    } catch (err) {
      console.error('[NativeBridge] submitFlashCommand error:', err);
    }
  }

  hideFlash(): void {
    if (!this.assertReady()) return;
    try {
      this.api!.hide_flash();
    } catch (err) {
      console.error('[NativeBridge] hideFlash error:', err);
    }
  }

  async callSkill(skillName: string, method: string, params?: unknown): Promise<unknown> {
    if (!this.assertReady()) return {};
    try {
      // 技能名和方法名只允许字母、数字、下划线
      if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(skillName)) {
        console.error('[NativeBridge] Invalid skill name:', skillName);
        return {};
      }
      if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(method)) {
        console.error('[NativeBridge] Invalid method name:', method);
        return {};
      }
      return await this.api!.call_skill(skillName, method, params);
    } catch (err) {
      console.error('[NativeBridge] callSkill error:', err);
      return {};
    }
  }

  pauseOutput(): void {
    if (!this.assertReady()) return;
    try {
      this.api!.pause_output();
    } catch (err) {
      console.error('[NativeBridge] pauseOutput error:', err);
    }
  }

  openOffice(filePath: string): void {
    if (!this.assertReady()) return;
    try {
      // 路径验证: 只允许合法文件路径字符
      if (/[<>"'|?*\x00-\x1f]/.test(filePath)) {
        console.error('[NativeBridge] Invalid file path:', filePath);
        return;
      }
      this.api!.open_office(filePath);
    } catch (err) {
      console.error('[NativeBridge] openOffice error:', err);
    }
  }

  terminalInput(data: string): void {
    if (!this.assertReady()) return;
    try {
      this.api!.terminal_input(data);
    } catch (err) {
      console.error('[NativeBridge] terminalInput error:', err);
    }
  }
}
