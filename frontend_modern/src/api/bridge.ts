/**
 * Butler Bridge: 前端与 Python 后端通信的统一接口
 *
 * 在 pywebview 环境中使用 bridge-native.ts (通过 window.pywebview.api)
 * 在浏览器开发环境中使用 bridge-web.ts (mock 实现)
 */

export interface ButlerBridge {
  /** 发送用户命令到后端 AI 处理 */
  handleCommand(command: string): Promise<void>;

  /** 提交快捷浮窗命令 (flash_input) */
  submitFlashCommand(command: string): void;

  /** 隐藏快捷浮窗 */
  hideFlash(): void;

  /** 调用指定技能的方法 */
  callSkill(skillName: string, method: string, params?: unknown): Promise<unknown>;

  /** 暂停当前 AI 输出流 */
  pauseOutput(): void;

  /** 用系统默认程序打开文件 */
  openOffice(filePath: string): void;

  /** 向终端发送输入数据 */
  terminalInput(data: string): void;
}
