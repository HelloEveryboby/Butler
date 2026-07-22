/**
 * OnboardingTour: 新手引导系统
 *
 * 引导新用户了解 Butler 的 2x2 矩阵界面。
 * 替代原来的全局 window.startOnboardingTour 等函数。
 */

import type { MatrixController } from '@/components/matrix/MatrixController';
import { toast } from '@/utils/toast';

interface OnboardingStep {
  title: string;
  text: string;
  quadrant: [number, number];
  highlightCell: string;
}

const STEPS: OnboardingStep[] = [
  {
    title: '🪐 核心对话中枢 (0,0)',
    text: '这是 Butler 的 AI 大脑。在此发送消息、拖放截图激光诊断报错，或点击下方快捷指令卡片一键触发自检、清理、音频降噪等自研底层核心能力。',
    quadrant: [0, 0],
    highlightCell: 'cell-0-0',
  },
  {
    title: '🕰️ 全局状态时光机 (1,0)',
    text: '全局可观测时光机。拖动底部时间轴滑块，可以重现系统历史快照和环境传感器遥测曲线，报错状态还会全局高亮提示！',
    quadrant: [1, 0],
    highlightCell: 'cell-1-0',
  },
  {
    title: '📊 任务画布 DAG Canvas (0,1)',
    text: '发光实体连接线任务编排。拖拽技能到此处可以组装复杂的 DAG 流水线。右上角更拥有全新启动控制台，点击即刻产生高对比度连线跑马灯流动！',
    quadrant: [0, 1],
    highlightCell: 'cell-0-1',
  },
  {
    title: '📦 技能仓储与底层硬件 (1,1)',
    text: '模块化抽屉式技能。One Folder = One Skill。在此浏览各种定制技能与文件仓。右上角可展开终端，监控底层 HAL 硬件传感器与多端 Go 运行器生命周期。',
    quadrant: [1, 1],
    highlightCell: 'cell-1-1',
  },
];

export class OnboardingTour {
  private matrix: MatrixController;
  private currentStep = 0;
  private overlay: HTMLElement | null = null;

  constructor(matrix: MatrixController) {
    this.matrix = matrix;
    this.overlay = document.getElementById('onboarding-tour-overlay');
  }

  /**
   * 开始引导
   */
  start(): void {
    this.currentStep = 0;
    if (this.overlay) {
      this.overlay.classList.add('active');
    }
    this.showStep(0);
  }

  /**
   * 下一步
   */
  next(): void {
    this.currentStep++;
    if (this.currentStep < STEPS.length) {
      this.showStep(this.currentStep);
    } else {
      this.complete();
    }
  }

  /**
   * 跳过引导
   */
  skip(): void {
    this.complete();
  }

  private showStep(index: number): void {
    const step = STEPS[index];
    if (!step) return;

    // 导航到对应象限
    this.matrix.moveTo(step.quadrant[0], step.quadrant[1]);

    // 高亮目标单元格
    document.querySelectorAll('.matrix-cell').forEach((cell) => {
      cell.classList.remove('onboarding-highlight');
    });
    const target = document.getElementById(step.highlightCell);
    if (target) {
      target.classList.add('onboarding-highlight');
    }

    // 更新 overlay 内容 (如果存在)
    if (this.overlay) {
      const titleEl = this.overlay.querySelector('.onboarding-title');
      const textEl = this.overlay.querySelector('.onboarding-text');
      const progressEl = this.overlay.querySelector('.onboarding-progress');

      if (titleEl) titleEl.innerHTML = step.title;
      if (textEl) textEl.innerHTML = step.text;
      if (progressEl) {
        progressEl.textContent = `${index + 1} / ${STEPS.length}`;
      }
    }
  }

  private complete(): void {
    if (this.overlay) {
      this.overlay.classList.remove('active');
    }

    // 清除高亮
    document.querySelectorAll('.matrix-cell').forEach((cell) => {
      cell.classList.remove('onboarding-highlight');
    });

    // 回到 (0,0)
    this.matrix.moveTo(0, 0);

    // 标记完成
    document.body.classList.add('onboarding-completed');
    localStorage.setItem('butler_onboarding_completed', 'true');

    toast.info('上手指南', '新手引导已结束。点击开始体验 Butler 本地优先的极致魅力！');
  }
}
