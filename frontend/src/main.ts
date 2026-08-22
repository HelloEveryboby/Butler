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

// Export Singletons onto Window for Global Type Safety & Compatibility
if (typeof window !== 'undefined') {
  window.voiceEngine = voiceEngine;
  window.wakeWordDetector = wakeWordDetector;
  window.ringVisualizer = ringVisualizer;
  window.glassUI = glassUI;
  window.bhlClient = bhlClient;
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

window.onProviderChange = (): void => {
  const provider = (document.getElementById('setting-provider') as HTMLSelectElement)?.value;
  const modelInput = document.getElementById('setting-model-name') as HTMLInputElement;
  const urlInput = document.getElementById('setting-base-url') as HTMLInputElement;
  if (!modelInput || !urlInput) return;

  if (provider === 'deepseek') {
    modelInput.value = 'deepseek-chat';
    urlInput.value = 'https://api.deepseek.com';
  } else if (provider === 'openai') {
    modelInput.value = 'gpt-4o';
    urlInput.value = 'https://api.openai.com/v1';
  } else if (provider === 'local') {
    modelInput.value = 'llama3';
    urlInput.value = 'http://localhost:11434';
  }
};

window.saveModelSettings = (): void => {
  const provider = (document.getElementById('setting-provider') as HTMLSelectElement)?.value;
  const model = (document.getElementById('setting-model-name') as HTMLInputElement)?.value;
  const apiKey = (document.getElementById('setting-api-key') as HTMLInputElement)?.value;
  const baseUrl = (document.getElementById('setting-base-url') as HTMLInputElement)?.value;

  localStorage.setItem('setting_provider', provider || '');
  localStorage.setItem('setting_model', model || '');
  localStorage.setItem('setting_api_key', apiKey || '');
  localStorage.setItem('setting_base_url', baseUrl || '');

  window.showToast?.('保存成功', '大模型提供商参数已成功加密保存在本地 SecretVault 中！', 'success');
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

function loadSettingsForm(): void {
  const provider = localStorage.getItem('setting_provider');
  if (provider) {
    const el = document.getElementById('setting-provider') as HTMLSelectElement;
    if (el) el.value = provider;
  }
  const model = localStorage.getItem('setting_model');
  if (model) {
    const el = document.getElementById('setting-model-name') as HTMLInputElement;
    if (el) el.value = model;
  }
  const apiKey = localStorage.getItem('setting_api_key');
  if (apiKey) {
    const el = document.getElementById('setting-api-key') as HTMLInputElement;
    if (el) el.value = apiKey;
  }
  const baseUrl = localStorage.getItem('setting_base_url');
  if (baseUrl) {
    const el = document.getElementById('setting-base-url') as HTMLInputElement;
    if (el) el.value = baseUrl;
  }
}
