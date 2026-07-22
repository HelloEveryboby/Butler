import type { ButlerBridge } from './bridge';

/**
 * Web 调试桥接实现
 *
 * 在纯浏览器环境中模拟 pywebview API，支持前端独立开发调试。
 * 所有方法都会在 console 输出调用信息，AI 相关方法返回模拟响应。
 */
export class WebBridge implements ButlerBridge {
  async handleCommand(command: string): Promise<void> {
    console.warn('[WebBridge] handleCommand:', command);

    // 模拟 AI 流式响应
    const streamStart = (window as any).onAIStreamStart;
    const streamChunk = (window as any).onAIStreamChunk;
    const streamEnd = (window as any).onAIStreamEnd;

    streamStart?.();

    const mockResponse = [
      `🤖 [Web 调试模式]`,
      `\n\n收到命令: **${command}**`,
      `\n\n这是前端独立开发时的模拟响应。`,
      `\n实际功能需要通过 pywebview 连接 Python 后端。`,
      `\n\n> 提示: 运行 \`python -m frontend.program.modern_app\` 启动完整 Butler。`,
    ].join('');

    // 模拟逐字输出
    for (const char of mockResponse) {
      streamChunk?.(char);
      await sleep(15);
    }

    streamEnd?.();
  }

  submitFlashCommand(command: string): void {
    console.warn('[WebBridge] submitFlashCommand:', command);
    // Flash 模式下也触发命令处理
    this.handleCommand(command);
  }

  hideFlash(): void {
    console.warn('[WebBridge] hideFlash');
    // 模拟隐藏浮窗
    const flashContainer = document.querySelector('.flash-container');
    if (flashContainer) {
      (flashContainer as HTMLElement).style.display = 'none';
    }
  }

  async callSkill(skillName: string, method: string, params?: unknown): Promise<unknown> {
    console.warn('[WebBridge] callSkill:', { skillName, method, params });
    // 返回模拟数据
    return this.getMockSkillData(skillName, method);
  }

  pauseOutput(): void {
    console.warn('[WebBridge] pauseOutput');
  }

  openOffice(filePath: string): void {
    console.warn('[WebBridge] openOffice:', filePath);
    console.warn('[WebBridge] 文件打开需要 pywebview 环境');
  }

  terminalInput(data: string): void {
    console.warn('[WebBridge] terminalInput:', data);
  }

  /**
   * 根据技能名和方法返回模拟数据，方便前端开发调试
   */
  private getMockSkillData(skillName: string, method: string): unknown {
    const mocks: Record<string, Record<string, unknown>> = {
      workflow_engine: {
        list: {
          'wf-001': {
            name: '每日数据备份',
            status: 'running',
            current_step: 2,
            steps: [
              { intent: '扫描数据目录' },
              { intent: '压缩打包' },
              { intent: '上传至云存储' },
            ],
          },
          'wf-002': {
            name: '系统健康检查',
            status: 'completed',
            current_step: 3,
            steps: [
              { intent: '检查磁盘空间' },
              { intent: '检查内存使用' },
              { intent: '生成报告' },
            ],
          },
        },
      },
      system_monitor: {
        metrics: {
          cpu: 23,
          memory: 61,
          disk: 45,
          network: 12,
        },
      },
    };

    return mocks[skillName]?.[method] ?? {};
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
