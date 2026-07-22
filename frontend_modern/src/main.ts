/**
 * Butler 前端主入口 (v3 安全加固版)
 *
 * 初始化顺序:
 * 1. 错误边界 (最先)
 * 2. 样式
 * 3. 模块
 * 4. 全局回调注册
 * 5. 应用初始化
 */

// === 1. 错误边界 (必须最先加载) ===
import { initErrorBoundary } from '@/utils/error-boundary';
initErrorBoundary();

// === 2. 样式导入 ===
import '@/styles/reset.css';
import '@/styles/variables.css';
import '@/styles/glassmorphism.css';
import '@/styles/animations.css';
import '@/styles/global.css';
import '@/styles/mobile.css';

// === 3. 模块导入 ===
import { bridge } from '@/api';
import { stateMatrix } from '@/stores/state-matrix';
import { chatStore } from '@/stores/chat-store';
import { MatrixController } from '@/components/matrix';
import { MobileNav } from '@/components/mobile-nav';
import { ChatPanel } from '@/components/chat';
import { DagEngine } from '@/components/dag';
import { TimeMachine } from '@/components/timemachine';
import { SkillLoader } from '@/components/skills';
import { TelemetryPanel } from '@/components/telemetry';
import { OnboardingTour } from '@/onboarding';
import { toast } from '@/utils/toast';
import { escapeHTML } from '@/utils/escape';
import { sanitizeCommand, checkRateLimit } from '@/utils/security';

// === 4. 全局函数注册 (兼容 pywebview evaluate_js) ===
// Python 后端通过 evaluate_js 调用这些函数名，保持不变
window.escapeHTML = escapeHTML;
window.showToast = (title, msg, type) => toast.show(title, msg, type as any);

// AI 流式响应回调 → 转发到 chatStore
window.onAIStreamStart = () => chatStore.startStream();
window.onAIStreamChunk = (chunk: string) => chatStore.appendChunk(chunk);
window.onAIStreamEnd = () => chatStore.endStream();

window.triggerQuickAction = (command: string, _emoji: string) => {
  const chatInput = document.getElementById('chat-input');
  const welcome = document.querySelector('.welcome-message');
  if (chatInput) {
    chatInput.innerText = command;
    if (welcome) (welcome as HTMLElement).style.display = 'none';
    const sendBtn = document.getElementById('send-command-btn');
    if (sendBtn) sendBtn.click();
  }
};

window.toggleInterfaceMode = () => {
  const select = document.getElementById('setting-interface-mode') as HTMLSelectElement;
  if (!select) return;

  const val = select.value;
  document.body.classList.add('interface-switching');

  setTimeout(() => {
    if (val === 'mobile') {
      document.body.classList.remove('interface-desktop');
      document.body.classList.add('interface-mobile');
      localStorage.setItem('setting_interface_mode', 'mobile');
      toast.show('操作界面', '已切换至手机端模拟界面模式。', 'success');
    } else {
      document.body.classList.remove('interface-mobile');
      document.body.classList.add('interface-desktop');
      localStorage.setItem('setting_interface_mode', 'desktop');
      toast.show('操作界面', '已切换至电脑端界面模式。', 'success');
    }

    setTimeout(() => {
      document.body.classList.remove('interface-switching');
    }, 150);
  }, 150);
};

// === 5. 应用初始化 ===
document.addEventListener('DOMContentLoaded', () => {
  console.warn('[Butler] Initializing frontend (v3 secure)...');

  // 初始化核心控制器
  const matrix = new MatrixController();
  const mobileNav = new MobileNav();
  const chat = new ChatPanel(bridge);
  const dag = new DagEngine();
  const timemachine = new TimeMachine();
  const skills = new SkillLoader();
  const telemetry = new TelemetryPanel();

  // 暴露到 window (过渡期兼容)
  window.matrix = matrix;

  // 新手引导
  if (!localStorage.getItem('butler_onboarding_completed')) {
    const tour = new OnboardingTour(matrix);
    tour.start();
    window.startOnboardingTour = () => tour.start();
    window.nextOnboardingStep = () => tour.next();
    window.skipOnboarding = () => tour.skip();
  }

  // 恢复界面模式偏好
  const savedMode = localStorage.getItem('setting_interface_mode');
  if (savedMode === 'mobile') {
    document.body.classList.remove('interface-desktop');
    document.body.classList.add('interface-mobile');
  }

  console.warn('[Butler] Frontend initialized successfully (v3 secure)');
});
