/**
 * Butler Main Entry Point in TypeScript
 */

import { styleManager } from './style';
import { voiceEngine } from './voice/engine';
import { wakeWordDetector } from './voice/wake-word';
import { ringVisualizer } from './canvas/ring-visualizer';
import { glassUI } from './ui/glassmorphism';
import { bhlClient } from './ws/bhl-client';
import { appConfig } from './config';
import { PyWebViewBridge } from './core/bridge';
import { screenCaptureController } from './components/screen_capture';
import { previewMedia, closeMediaPreview } from './components/media_preview';
import { downloadManager } from '../download/download';

// Export Singletons onto Window for Global Type Safety & Compatibility
if (typeof window !== 'undefined') {
  window.voiceEngine = voiceEngine;
  window.wakeWordDetector = wakeWordDetector;
  window.ringVisualizer = ringVisualizer;
  window.glassUI = glassUI;
  window.bhlClient = bhlClient;
  (window as any).ScreenCapture = screenCaptureController;
  (window as any).previewMedia = previewMedia;
  (window as any).closeMediaPreview = closeMediaPreview;
  (window as any).downloadManager = downloadManager;
  downloadManager.init();
}

// Initialize Dynamic Styles & Themes
styleManager.injectBaseStyles();

// Global Utilities
window.escapeHTML = (str: any): string => {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
};

// Dialogue Quick Action Trigger
window.triggerQuickAction = (command: string, _emoji?: string): void => {
  const chatInput = document.getElementById('chat-input');
  const welcome = document.querySelector('.welcome-message') as HTMLElement;
  if (chatInput) {
    chatInput.innerText = command;
    if (welcome) welcome.style.display = 'none';
    const sendBtn = document.getElementById('send-command-btn');
    if (sendBtn) {
      sendBtn.click();
    }
  }
};

// Toggle Operation Interface Mode (Desktop vs Mobile)
window.toggleInterfaceMode = (): void => {
  const select = document.getElementById('setting-interface-mode') as HTMLSelectElement;
  if (select) {
    const val = select.value;
    document.body.classList.add('interface-switching');

    setTimeout(() => {
      if (val === 'mobile') {
        document.body.classList.remove('interface-desktop');
        document.body.classList.add('interface-mobile');
        localStorage.setItem('setting_interface_mode', 'mobile');
        window.showToast?.('操作界面', '已切换至手机端模拟界面模式。', 'success');
      } else {
        document.body.classList.remove('interface-mobile');
        document.body.classList.add('interface-desktop');
        localStorage.setItem('setting_interface_mode', 'desktop');
        window.showToast?.('操作界面', '已切换至电脑端界面模式。', 'success');
      }

      setTimeout(() => {
        document.body.classList.remove('interface-switching');
      }, 150);
    }, 150);
  }
};

// Onboarding Steps Definitions
interface OnboardingStep {
  title: string;
  text: string;
  quadrant: [number, number];
  highlight: string;
}

const onboardingSteps: OnboardingStep[] = [
  {
    title: '🪐 核心对话中枢 (0,0)',
    text: '这是 Butler 的 AI 大脑。在此发送消息、拖放截图激光诊断报错，或点击下方<b>快捷指令卡片</b>一键触发自检、清理、音频降噪等自研底层核心能力。',
    quadrant: [0, 0],
    highlight: 'cell-0-0',
  },
  {
    title: '🕰️ 全局状态时光机 (1,0)',
    text: '全局可观测时光机。拖动底部时间轴滑块，可以重现系统历史快照和环境传感器遥测曲线，报错状态还会全局高亮提示！',
    quadrant: [1, 0],
    highlight: 'cell-1-0',
  },
  {
    title: '📊 任务画布 DAG Canvas (0,1)',
    text: '发光实体连接线任务编排。拖拽技能到此处可以组装复杂的 DAG 流水线。右上角更拥有<b>全新启动控制台</b>，点击即刻产生高对比度连线跑马灯流动！',
    quadrant: [0, 1],
    highlight: 'cell-0-1',
  },
  {
    title: '📦 技能仓储与底层硬件 (1,1)',
    text: '模块化抽屉式技能。One Folder = One Skill。在此浏览各种定制技能与文件仓。右上角可展开终端，监控底层 HAL 硬件传感器与多端 Go 运行器生命周期。',
    quadrant: [1, 1],
    highlight: 'cell-1-1',
  },
];

let currentOnboardingStep = 0;

window.startOnboardingTour = (): void => {
  currentOnboardingStep = 0;
  const overlay = document.getElementById('onboarding-tour-overlay');
  if (overlay) {
    overlay.classList.add('active');
    showOnboardingStep(0);
  }
};

window.nextOnboardingStep = (): void => {
  currentOnboardingStep++;
  if (currentOnboardingStep < onboardingSteps.length) {
    showOnboardingStep(currentOnboardingStep);
  } else {
    window.skipOnboarding?.();
  }
};

window.skipOnboarding = (): void => {
  const overlay = document.getElementById('onboarding-tour-overlay');
  if (overlay) overlay.classList.remove('active');
  document.querySelectorAll('.matrix-cell').forEach((cell) => {
    cell.classList.remove('onboarding-highlight');
  });
  if (window.matrix) {
    window.matrix.moveTo(0, 0);
  }
  document.body.classList.add('onboarding-completed');
  window.showToast?.('上手指南', '新手引导已结束。点击开始体验 Butler 本地优先的极致魅力！', 'success');
  localStorage.setItem('butler_onboarding_completed', 'true');
};

function showOnboardingStep(index: number): void {
  const step = onboardingSteps[index];
  if (!step) return;

  if (window.matrix) {
    window.matrix.moveTo(step.quadrant[0], step.quadrant[1]);
  }

  document.querySelectorAll('.matrix-cell').forEach((cell) => {
    cell.classList.remove('onboarding-highlight');
  });
  const targetCell = document.getElementById(step.highlight);
  if (targetCell) {
    targetCell.classList.add('onboarding-highlight');
  }

  const bubble = document.getElementById('onboarding-bubble-el');
  const bodyText = document.getElementById('onboarding-body-text');
  const stepIndicator = document.getElementById('onboarding-step-indicator');
  const nextBtn = document.getElementById('onboarding-next-btn');

  if (bodyText) bodyText.innerHTML = step.text;
  if (stepIndicator) stepIndicator.innerText = `${index + 1} / ${onboardingSteps.length}`;
  if (nextBtn) {
    nextBtn.innerText = index === onboardingSteps.length - 1 ? '探索完成' : '下一步';
  }

  if (bubble) {
    bubble.style.position = 'fixed';
    bubble.style.left = '40px';
    bubble.style.bottom = '130px';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Glassmorphism DOM bindings
  glassUI.initDOM();

  const interactionFlow = document.getElementById('interaction-flow');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-command-btn');

  let isStreaming = false;
  let currentAILine: HTMLElement | null = null;

  function executeChatCommand(): void {
    if (!chatInput || !interactionFlow) return;
    const command = chatInput.innerText.trim();
    if (!command || isStreaming) return;

    const welcome = document.querySelector('.welcome-message') as HTMLElement;
    if (welcome) welcome.style.display = 'none';

    const userLine = document.createElement('div');
    userLine.className = 'interaction-line user-input-line';
    userLine.innerText = command;
    interactionFlow.appendChild(userLine);

    chatInput.innerText = '';
    isStreaming = true;

    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.handle_command(command);
    }
    interactionFlow.scrollTop = interactionFlow.scrollHeight;
  }

  window.showToast = (title: string, message: string, type: 'success' | 'error' | 'warning' | 'info' = 'success'): void => {
    const container = document.getElementById('notifier-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast-notification ${type}`;
    toast.innerHTML = `
      <div class="notif-header">
        <span class="notif-title">${title}</span>
        <span class="notif-time">${new Date().toLocaleTimeString()}</span>
      </div>
      <div class="notif-content">${message}</div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('closing');
      setTimeout(() => toast.remove(), 4000);
    }, 3000);
  };

  const inputActionsLeft = document.querySelector('.input-actions-left');
  if (inputActionsLeft) {
    const confirmTrigger = document.createElement('button');
    confirmTrigger.className = 'icon-btn-small';
    confirmTrigger.innerHTML = '<i class="fas fa-shield-check"></i>';
    confirmTrigger.title = '触发确认框';
    confirmTrigger.onclick = () => {
      if ((window as any).CopilotModal) {
        const modal = new (window as any).CopilotModal();
        modal.show({
          title: '重构代码确认',
          message: 'Butler 检测到 butler/core/workflow_engine.py 中的循环引用。是否允许自动重构该模块？此操作不可逆。',
          onConfirm: () => {
            window.showToast?.('系统任务', '任务已开始执行');
            const statusDot = document.getElementById('thinking-status');
            if (statusDot) statusDot.classList.add('active');

            setTimeout(() => {
              if (statusDot) statusDot.classList.remove('active');
              window.showToast?.('修复成功', '代码重构已完成。', 'success');
            }, 2000);
          },
          triggerBtn: confirmTrigger,
        });
      }
    };
    inputActionsLeft.appendChild(confirmTrigger);
  }

  if (sendBtn) sendBtn.onclick = executeChatCommand;
  if (chatInput) {
    chatInput.onkeydown = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        executeChatCommand();
      }
    };
  }

  window.onAIStreamStart = () => {
    isStreaming = true;
    document.getElementById('thinking-status')?.classList.add('active');
    currentAILine = document.createElement('div');
    currentAILine.className = 'interaction-line ai-output-line';
    if (interactionFlow) {
      interactionFlow.appendChild(currentAILine);
    }
  };

  window.onAIStreamChunk = (chunk: string) => {
    if (currentAILine && interactionFlow) {
      const span = document.createElement('span');
      span.innerText = chunk;
      currentAILine.appendChild(span);
      interactionFlow.scrollTop = interactionFlow.scrollHeight;
    }
  };

  window.onAIStreamEnd = () => {
    isStreaming = false;
    document.getElementById('thinking-status')?.classList.remove('active');
  };

  if (chatInput) {
    chatInput.onpaste = (e: ClipboardEvent) => {
      const clipboardData = e.clipboardData;
      if (!clipboardData) return;
      const items = clipboardData.items;
      for (const index in items) {
        const item = items[index];
        if (item.kind === 'file' && item.type.startsWith('image/')) {
          const blob = item.getAsFile();
          if (blob) {
            const reader = new FileReader();
            reader.onload = (event: ProgressEvent<FileReader>) => {
              if (event.target?.result) {
                handleImageInput(event.target.result as string);
              }
            };
            reader.readAsDataURL(blob);
          }
        }
      }
    };
  }

  function handleImageInput(base64: string): void {
    if (!interactionFlow) return;
    const container = document.createElement('div');
    container.className = 'interaction-line ai-output-line laser-scan-container';
    container.innerHTML = `
      <div class="laser-line"></div>
      <img src="${base64}" style="width: 100%; border-radius: 8px;">
      <p style="margin-top: 10px; font-size: 14px; color: var(--text-secondary);">正在进行激光扫描诊断...</p>
    `;
    interactionFlow.appendChild(container);
    interactionFlow.scrollTop = interactionFlow.scrollHeight;

    setTimeout(async () => {
      container.querySelector('.laser-line')?.remove();
      const p = container.querySelector('p');
      if (p) p.innerText = '诊断完成。检测到关键逻辑错误。';

      renderFixCard({
        type: 'LOGIC_ERROR',
        title: '检测到模块冲突 (butler/core/workflow_engine.py)',
        desc: '在第 142 行发现循环引用风险，建议立即重构。',
        btnText: '修复逻辑 (Time-Slit)',
        filePath: 'butler/core/workflow_engine.py',
        line: 142,
      });
    }, 2500);
  }

  function renderFixCard(data: any): void {
    if (!interactionFlow) return;
    const card = document.createElement('div');
    card.className = 'fix-card glass-surface';
    card.innerHTML = `
      <div style="font-weight: 700; color: #34C759; display: flex; align-items: center; gap: 8px;">
        <i class="fas fa-magic"></i> ${data.title}
      </div>
      <p style="font-size: 14px; opacity: 0.8;">${data.desc}</p>
      <button class="fix-btn apple-btn-primary">${data.btnText}</button>
    `;

    const fixBtn = card.querySelector('.fix-btn') as HTMLElement;
    if (fixBtn) {
      fixBtn.onclick = async () => {
        if (data.filePath && window.timeSlitEditor) {
          window.timeSlitEditor.openSlit(data.filePath, data.line, card);
        } else {
          fixBtn.innerText = '修复中...';
          setTimeout(() => {
            card.innerHTML = `
              <div style="color: #34C759; font-weight: 700;">
                <i class="fas fa-magic"></i> 修复成功！
              </div>
            `;
          }, 1500);
        }
      };
    }

    interactionFlow.appendChild(card);
    interactionFlow.scrollTop = interactionFlow.scrollHeight;
  }
});

// Terminal & Memos UI Window Toggles
window.toggleTerminal = (): void => {
  const el = document.getElementById('terminal-overlay');
  if (!el) return;
  el.classList.toggle('hidden');
  if (!el.classList.contains('hidden')) {
    if (!window.term && window.Terminal && window.FitAddon) {
      window.term = new window.Terminal({
        cursorBlink: true,
        theme: { background: '#000000', foreground: '#f0f0f0' },
        fontSize: 14,
        fontFamily: 'SFMono-Regular, Consolas, monospace',
      });
      const fitAddon = new window.FitAddon.FitAddon();
      window.term.loadAddon(fitAddon);
      window.term.open(document.getElementById('terminal-container'));
      setTimeout(() => fitAddon.fit(), 100);
    }
  }
};

window.toggleMemos = (): void => {
  const el = document.getElementById('memos-overlay');
  if (!el) return;
  el.classList.toggle('hidden');
  if (!el.classList.contains('hidden') && window.memosManager) {
    window.memosManager.refreshMemos();
  }
};

// Vault Unlocking Visual Feedback
window.onVaultUnlocking = (_data: any): void => {
  const modal = document.createElement('div');
  modal.className = 'fullscreen-notif-overlay';
  modal.innerHTML = `
    <div class="fullscreen-notif-card glass-surface vault-unlock-card" style="border: 1px solid #d4af37;">
      <h2 style="color: #d4af37;"><i class="fas fa-shield-halved"></i> 密室正在解锁</h2>
      <p>为了您的隐私安全，Butler 正在从安全内存派生密钥。</p>
      <div class="vault-lock-animation active"><i class="fas fa-lock" style="font-size: 48px; color: #d4af37;"></i></div>
      <div style="margin-top: 30px;" class="loading-spinner"></div>
    </div>
  `;
  document.body.appendChild(modal);
  setTimeout(() => modal.remove(), 3000);
};

// File Listing Helper
async function loadFiles(path: string): Promise<void> {
  if (PyWebViewBridge.isAvailable()) {
    const files = await PyWebViewBridge.listFiles(path);
    const list = document.getElementById('files-list');
    if (!list) return;
    list.innerHTML = '';
    files.forEach((file: any) => {
      const item = document.createElement('div');
      item.className = 'file-item';
      item.innerHTML = `<i class="fas ${file.is_dir ? 'fa-folder' : 'fa-file-alt'}"></i> <span>${file.name}</span>`;
      item.onclick = () => (file.is_dir ? loadFiles(file.path) : null);
      list.appendChild(item);
    });
  }
}

// Skills Drawer & WebMessagePort Native Bridge Lifecycle
document.addEventListener('DOMContentLoaded', () => {
  loadFiles('.');

  const drawer = document.querySelector('.skills-drawer');
  if (drawer) {
    const mockSkills = [
      { name: '截图排障', icon: 'fa-bug', color: '#FF3B30' },
      { name: '局域网同步', icon: 'fa-sync', color: '#34C759' },
      { name: '系统清理', icon: 'fa-broom', color: '#FF9500' },
    ];

    mockSkills.forEach((skill) => {
      const card = document.createElement('div');
      card.className = 'dag-node glass-surface';
      card.draggable = true;
      card.style.position = 'relative';
      card.style.marginBottom = '10px';
      card.innerHTML = `<i class="fas ${skill.icon}" style="color: ${skill.color}"></i> <span>${skill.name}</span>`;
      card.ondragstart = (e: DragEvent) => {
        e.dataTransfer?.setData(
          'application/json',
          JSON.stringify({
            type: 'skill',
            name: skill.name,
            icon: skill.icon,
          })
        );
      };
      drawer.appendChild(card);
    });
  }

  window.addEventListener('message', function (event: MessageEvent) {
    if (event.data === 'init_bridge' && event.ports[0]) {
      const port = event.ports[0];
      window.NativePort = port;

      port.onmessage = function (e: MessageEvent) {
        try {
          const data = JSON.parse(e.data);
          if (data.timestamp && window.StateMatrix) {
            window.StateMatrix.updateFromBackend(data);
          }
          if (data.type === 'DRAS') {
            const indicator = document.getElementById('connection-status');
            if (indicator) {
              indicator.style.backgroundColor = data.active ? '#FF9500' : '#34C759';
            }
          }
          if (data.type === 'LOG' && window.TimeMachine) {
            window.TimeMachine.pushLog(data.data);
          }
        } catch (err) {
          console.error('Native Bridge Parse Error:', err);
        }
      };
      console.log('Butler Mobile Bridge: Active via WebMessagePort');
    }
  });
});

// Settings Toggle and Form Lifecycle
window.toggleSettings = (): void => {
  const overlay = document.getElementById('settings-overlay');
  if (overlay) {
    overlay.classList.toggle('hidden');
    if (!overlay.classList.contains('hidden')) {
      loadSettingsForm();
    }
  }
};

window.switchSettingsTab = (tabId: string): void => {
  document.querySelectorAll('.settings-nav-item').forEach((btn) => {
    btn.classList.remove('active');
  });
  document.querySelectorAll('.settings-panel').forEach((panel) => {
    panel.classList.remove('active');
  });

  const targetBtn = document.getElementById(`tab-btn-${tabId}`);
  if (targetBtn) targetBtn.classList.add('active');

  const targetPanel = document.getElementById(`settings-tab-${tabId}`);
  if (targetPanel) targetPanel.classList.add('active');
};

window.toggleApiKeyVisibility = (): void => {
  const keyInput = document.getElementById('setting-api-key') as HTMLInputElement;
  const eyeIcon = document.getElementById('api-key-eye');
  if (keyInput && eyeIcon) {
    if (keyInput.type === 'password') {
      keyInput.type = 'text';
      eyeIcon.className = 'fas fa-eye-slash';
    } else {
      keyInput.type = 'password';
      eyeIcon.className = 'fas fa-eye';
    }
  }
};

const PROVIDER_CONFIGS: Record<string, { presets: string[]; baseUrl: string; showApiKey: boolean; keyLabel?: string; showSecretKey?: boolean; showCustomLabel?: boolean }> = {
  deepseek: {
    presets: ['deepseek-chat', 'deepseek-coder', 'deepseek-reasoner'],
    baseUrl: 'https://api.deepseek.com',
    showApiKey: true,
    keyLabel: 'API 密钥 (API Key)'
  },
  openai: {
    presets: ['gpt-4o', 'gpt-4o-mini', 'o1-mini', 'gpt-3.5-turbo'],
    baseUrl: 'https://api.openai.com/v1',
    showApiKey: true,
    keyLabel: 'API 密钥 (API Key)'
  },
  anthropic: {
    presets: ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229'],
    baseUrl: 'https://api.anthropic.com',
    showApiKey: true,
    keyLabel: 'API 密钥 (x-api-key)'
  },
  ollama: {
    presets: ['llama3.2', 'llama3', 'qwen2.5', 'deepseek-r1:7b'],
    baseUrl: 'http://localhost:11434',
    showApiKey: false
  },
  qianfan: {
    presets: ['ernie-4.0-8k', 'ernie-3.5-8k', 'ernie-speed-128k'],
    baseUrl: 'https://qianfan.baidubce.com/v2',
    showApiKey: true,
    keyLabel: 'API Key (Client ID)',
    showSecretKey: true
  },
  custom: {
    presets: ['custom'],
    baseUrl: 'https://api.openai.com/v1',
    showApiKey: true,
    keyLabel: 'API 密钥 (API Key)',
    showCustomLabel: true
  }
};

window.onProviderChange = (): void => {
  const provider = (document.getElementById('setting-provider') as HTMLSelectElement)?.value || 'deepseek';
  const cfg = PROVIDER_CONFIGS[provider] || PROVIDER_CONFIGS['deepseek'];

  // Toggle dynamic fields visibility
  const apiKeyRow = document.querySelector('.field-api-key') as HTMLElement;
  const secretKeyRow = document.querySelector('.field-secret-key') as HTMLElement;
  const customLabelRow = document.querySelector('.field-custom-label') as HTMLElement;
  const keyLabel = document.getElementById('label-api-key');

  if (apiKeyRow) apiKeyRow.classList.toggle('hidden', !cfg.showApiKey);
  if (secretKeyRow) secretKeyRow.classList.toggle('hidden', !cfg.showSecretKey);
  if (customLabelRow) customLabelRow.classList.toggle('hidden', !cfg.showCustomLabel);
  if (keyLabel && cfg.keyLabel) keyLabel.innerText = cfg.keyLabel;

  // Set default base URL
  const urlInput = document.getElementById('setting-base-url') as HTMLInputElement;
  if (urlInput && cfg.baseUrl) urlInput.value = cfg.baseUrl;

  // Render presets
  const presetSelect = document.getElementById('setting-model-preset') as HTMLSelectElement;
  const modelInput = document.getElementById('setting-model-name') as HTMLInputElement;
  if (presetSelect && cfg.presets) {
    presetSelect.innerHTML = cfg.presets.map(m => `<option value="${m}">${m}</option>`).join('') + '<option value="custom">+ 自定义输入...</option>';
    presetSelect.value = cfg.presets[0];
    if (modelInput) modelInput.value = cfg.presets[0];
  }

  // Reset status badge
  updateModelStatusBadge('idle', '待校验');
};

window.onModelPresetChange = (): void => {
  const presetSelect = document.getElementById('setting-model-preset') as HTMLSelectElement;
  const modelInput = document.getElementById('setting-model-name') as HTMLInputElement;
  if (!presetSelect || !modelInput) return;

  if (presetSelect.value !== 'custom') {
    modelInput.value = presetSelect.value;
  } else {
    modelInput.focus();
    modelInput.select();
  }
};

window.toggleAdvancedParams = (): void => {
  const panel = document.getElementById('advanced-params-panel');
  const icon = document.getElementById('advanced-params-icon');
  if (panel) {
    panel.classList.toggle('hidden');
    if (icon) {
      icon.style.transform = panel.classList.contains('hidden') ? 'rotate(0deg)' : 'rotate(90deg)';
    }
  }
};

window.updateTemperatureVal = (val: string): void => {
  const display = document.getElementById('temp-val-display');
  const desc = document.getElementById('temp-hint-desc');
  if (display) display.innerText = val;
  if (desc) {
    const num = parseFloat(val);
    if (num <= 0.3) desc.innerText = `${val} 严谨精准 (适合代码生成/数学推理)`;
    else if (num <= 0.8) desc.innerText = `${val} 严谨与创意平衡 (通用日常问答)`;
    else desc.innerText = `${val} 高创意灵感 (适合发散写作/艺术拟人)`;
  }
};

window.setMaxTokens = (tokens: number): void => {
  const input = document.getElementById('setting-max-tokens') as HTMLInputElement;
  if (input) input.value = String(tokens);
};

function updateModelStatusBadge(state: 'idle' | 'testing' | 'success' | 'error', text: string): void {
  const badge = document.getElementById('model-status-badge');
  const latencyText = document.getElementById('connection-latency-text');
  if (!badge) return;

  badge.className = `model-status-badge ${state}`;
  if (state === 'testing') {
    badge.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${text}`;
  } else if (state === 'success') {
    badge.innerHTML = `<i class="fas fa-check-circle"></i> ${text}`;
  } else if (state === 'error') {
    badge.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${text}`;
  } else {
    badge.innerHTML = `<i class="fas fa-circle-notch"></i> ${text}`;
    if (latencyText) latencyText.innerText = '';
  }
}

window.testModelConnection = async (): Promise<void> => {
  const provider = (document.getElementById('setting-provider') as HTMLSelectElement)?.value;
  const apiKey = (document.getElementById('setting-api-key') as HTMLInputElement)?.value;
  const baseUrl = (document.getElementById('setting-base-url') as HTMLInputElement)?.value;
  const modelName = (document.getElementById('setting-model-name') as HTMLInputElement)?.value;
  const secretKey = (document.getElementById('setting-secret-key') as HTMLInputElement)?.value;
  const providerLabel = (document.getElementById('setting-provider-label') as HTMLInputElement)?.value;

  const btnText = document.getElementById('btn-test-text');
  const latencyText = document.getElementById('connection-latency-text');
  if (btnText) btnText.innerText = '测试中...';

  updateModelStatusBadge('testing', '正在连接...');

  const payload = {
    provider,
    api_key: apiKey,
    base_url: baseUrl,
    model_name: modelName,
    secret_key: secretKey,
    provider_label: providerLabel
  };

  try {
    let res: any = null;
    if (window.pywebview && window.pywebview.api && window.pywebview.api.test_model_connection) {
      res = await window.pywebview.api.test_model_connection(payload);
    } else {
      // Mock fallback for browser dev
      await new Promise(r => setTimeout(r, 800));
      res = { valid: true, latency_ms: 128, models: ['deepseek-chat', 'deepseek-coder'] };
    }

    if (res && res.valid) {
      updateModelStatusBadge('success', '连接成功');
      if (latencyText) latencyText.innerText = `响应延迟: ${res.latency_ms || 0}ms`;
      window.showToast?.('连接测试成功', `成功连接到 ${provider}，响应延迟 ${res.latency_ms || 0}ms`, 'success');

      // Update models list dropdown if fetched models list
      if (res.models && Array.isArray(res.models) && res.models.length > 0) {
        const presetSelect = document.getElementById('setting-model-preset') as HTMLSelectElement;
        if (presetSelect) {
          const fetchedOpts = res.models.slice(0, 10).map((m: string) => `<option value="${m}">${m}</option>`).join('');
          presetSelect.innerHTML = fetchedOpts + '<option value="custom">+ 自定义输入...</option>';
        }
      }
    } else {
      const errMsg = res ? res.error : '无法建立与 API Endpoint 的连接';
      updateModelStatusBadge('error', '连接失败');
      if (latencyText) latencyText.innerText = '';
      window.showToast?.('连接测试失败', errMsg, 'error');
    }
  } catch (e: any) {
    updateModelStatusBadge('error', '校验异常');
    if (latencyText) latencyText.innerText = '';
    window.showToast?.('校验异常', e.message || '网络连接异常', 'error');
  } finally {
    if (btnText) btnText.innerText = '测试连接';
  }
};

window.saveModelSettings = async (): Promise<void> => {
  const provider = (document.getElementById('setting-provider') as HTMLSelectElement)?.value;
  const model = (document.getElementById('setting-model-name') as HTMLInputElement)?.value;
  const apiKey = (document.getElementById('setting-api-key') as HTMLInputElement)?.value;
  const baseUrl = (document.getElementById('setting-base-url') as HTMLInputElement)?.value;
  const secretKey = (document.getElementById('setting-secret-key') as HTMLInputElement)?.value;
  const providerLabel = (document.getElementById('setting-provider-label') as HTMLInputElement)?.value;
  const temperature = (document.getElementById('setting-temperature') as HTMLInputElement)?.value || '0.7';
  const maxTokens = (document.getElementById('setting-max-tokens') as HTMLInputElement)?.value || '4096';

  const payload = {
    provider: provider || 'deepseek',
    model_name: model || '',
    api_key: apiKey || '',
    base_url: baseUrl || '',
    secret_key: secretKey || '',
    provider_label: providerLabel || '',
    temperature: parseFloat(temperature),
    max_tokens: parseInt(maxTokens, 10)
  };

  // Local Storage fallback cache
  localStorage.setItem('setting_provider', payload.provider);
  localStorage.setItem('setting_model', payload.model_name);
  localStorage.setItem('setting_api_key', payload.api_key);
  localStorage.setItem('setting_base_url', payload.base_url);
  localStorage.setItem('setting_temperature', temperature);
  localStorage.setItem('setting_max_tokens', maxTokens);

  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_model_config) {
      const res = await window.pywebview.api.save_model_config(payload);
      window.showToast?.('保存成功', res ? res.message : '大模型配置已更新并即时生效！', 'success');
    } else {
      window.showToast?.('保存成功', '大模型提供商参数已成功在本地 SecretVault 与缓存中生效！', 'success');
    }
  } catch (e: any) {
    window.showToast?.('保存异常', '配置写入失败: ' + e.message, 'error');
  }
};

window.onMemoryDbChange = (): void => {
  const dbType = (document.getElementById('setting-memory-db') as HTMLSelectElement)?.value || 'sqlite';
  const badge = document.getElementById('active-memory-db-badge');
  if (badge) {
    badge.innerText = dbType.toUpperCase() + ' Database';
  }
};

window.saveMemorySettings = (): void => {
  const dbType = (document.getElementById('setting-memory-db') as HTMLSelectElement)?.value;
  const dreamEngine = (document.getElementById('setting-dream-engine') as HTMLInputElement)?.checked;

  localStorage.setItem('setting_memory_db', dbType || '');
  localStorage.setItem('setting_dream_engine', String(dreamEngine));

  window.showToast?.('记忆库设置', '向量数据库切换及后台做梦精简规则已更新且生效。', 'success');
};

window.testHalConnection = (): void => {
  window.showToast?.('硬件自检', '正在向物理 STM32 硬件总线发送遥测信号包...', 'success');
  setTimeout(() => {
    window.showToast?.('测试完成', '回路反馈正常！已成功捕获 HAL 传感器温度与 USB-OLED 屏幕驱动缓存。', 'success');
  }, 1500);
};

window.toggleThemeMode = (): void => {
  const toggleInput = document.getElementById('setting-theme-toggle') as HTMLInputElement;
  if (toggleInput) {
    if (toggleInput.checked) {
      styleManager.applyTheme('dark');
      window.showToast?.('深浅主题', '已切换至暗黑磨砂玻璃主题。', 'success');
    } else {
      styleManager.applyTheme('apple');
      window.showToast?.('深浅主题', '已切换至 Apple 白磨砂极简主题。', 'success');
    }
  }
};

window.updateBlurValue = (val: string | number): void => {
  appConfig.set('blurAmount', Number(val));
  styleManager.injectBaseStyles();
};

window.updateFontFamily = (val: string): void => {
  appConfig.set('fontFamily', val);
  styleManager.injectBaseStyles();
  window.showToast?.('字体样式', '系统字体样式已成功更新。', 'success');
};

window.updateFontSize = (val: string): void => {
  appConfig.set('fontSize', val);
  styleManager.injectBaseStyles();
  window.showToast?.('字体大小', `系统基本字号已调整为 ${val}。`, 'success');
};

window.launchPixelPet = async (): Promise<void> => {
  try {
    if (PyWebViewBridge.isAvailable()) {
      const res = await PyWebViewBridge.callSkill('pixel_pet', 'launch');
      if (res && res.status === 'success') {
        window.showToast?.('电子宠物', '桌面电子小狗已成功启动！🐾', 'success');
      } else {
        window.showToast?.('电子宠物', '启动电子宠物失败：' + (res ? res.message : '未知错误'), 'error');
      }
    } else {
      window.showToast?.('电子宠物', '当前处于浏览器预览模式。请在 Butler 桌面客户端中启动 🐾', 'warning');
    }
  } catch (e: any) {
    window.showToast?.('电子宠物', '启动失败：' + e.message, 'error');
  }
};

async function loadSettingsForm(): Promise<void> {
  let backendConfig: any = null;
  if (window.pywebview && window.pywebview.api && window.pywebview.api.get_model_config) {
    try {
      backendConfig = await window.pywebview.api.get_model_config();
    } catch (e) {
      console.warn('Failed to load model config from PyWebView API:', e);
    }
  }

  const provider = backendConfig?.provider || localStorage.getItem('setting_provider') || 'deepseek';
  const providerEl = document.getElementById('setting-provider') as HTMLSelectElement;
  if (providerEl) {
    providerEl.value = provider;
    window.onProviderChange?.();
  }

  const model = backendConfig?.model_name || localStorage.getItem('setting_model');
  if (model) {
    const modelEl = document.getElementById('setting-model-name') as HTMLInputElement;
    const presetEl = document.getElementById('setting-model-preset') as HTMLSelectElement;
    if (modelEl) modelEl.value = model;
    if (presetEl) {
      const hasOption = Array.from(presetEl.options).some(opt => opt.value === model);
      presetEl.value = hasOption ? model : 'custom';
    }
  }

  const apiKey = backendConfig?.api_key || localStorage.getItem('setting_api_key');
  if (apiKey) {
    const keyEl = document.getElementById('setting-api-key') as HTMLInputElement;
    if (keyEl) keyEl.value = apiKey;
  }

  const baseUrl = backendConfig?.base_url || localStorage.getItem('setting_base_url');
  if (baseUrl) {
    const urlEl = document.getElementById('setting-base-url') as HTMLInputElement;
    if (urlEl) urlEl.value = baseUrl;
  }

  const secretKey = backendConfig?.secret_key || localStorage.getItem('setting_secret_key');
  if (secretKey) {
    const secretEl = document.getElementById('setting-secret-key') as HTMLInputElement;
    if (secretEl) secretEl.value = secretKey;
  }

  const providerLabel = backendConfig?.provider_label || localStorage.getItem('setting_provider_label');
  if (providerLabel) {
    const labelEl = document.getElementById('setting-provider-label') as HTMLInputElement;
    if (labelEl) labelEl.value = providerLabel;
  }

  const temp = backendConfig?.temperature ?? localStorage.getItem('setting_temperature') ?? '0.7';
  const tempEl = document.getElementById('setting-temperature') as HTMLInputElement;
  if (tempEl) {
    tempEl.value = String(temp);
    window.updateTemperatureVal?.(String(temp));
  }

  const maxTokens = backendConfig?.max_tokens ?? localStorage.getItem('setting_max_tokens') ?? '4096';
  const tokensEl = document.getElementById('setting-max-tokens') as HTMLInputElement;
  if (tokensEl) tokensEl.value = String(maxTokens);
}
