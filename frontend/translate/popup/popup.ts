/* ============================================================
   Popup — 弹窗控制面板
   ============================================================ */

import { loadConfig, saveConfig } from '../utils/storage';
import { sendMessage } from '../utils/messaging';
import { LANGUAGES } from '../utils/languages';
import { TranslateConfig, ProviderConfig } from '../utils/types';

async function init() {
  const config = await loadConfig();

  // 填充语言列表
  const langSelect = document.getElementById('target-lang') as HTMLSelectElement;
  for (const lang of LANGUAGES) {
    const opt = document.createElement('option');
    opt.value = lang.code;
    opt.textContent = `${lang.name}`;
    if (lang.code === config.targetLang) opt.selected = true;
    langSelect.appendChild(opt);
  }

  // 填充翻译源列表
  const providerSelect = document.getElementById('active-provider') as HTMLSelectElement;
  function refreshProviders() {
    providerSelect.innerHTML = '';
    for (const p of config.providers) {
      if (!p.enabled) continue;
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = p.name;
      if (p.id === config.activeProviderId) opt.selected = true;
      providerSelect.appendChild(opt);
    }
    updateProviderStatus();
  }
  refreshProviders();

  // 显示模式
  const modeBtns = document.querySelectorAll('.mode-btn') as NodeListOf<HTMLButtonElement>;
  modeBtns.forEach(btn => {
    if (btn.dataset.mode === config.displayMode) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
    btn.addEventListener('click', async () => {
      modeBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      await saveConfig({ displayMode: btn.dataset.mode as any });
      // 通知 content script 刷新
      sendToActiveTab({ type: 'RELOAD_CONFIG' });
    });
  });

  // 自动翻译
  const autoToggle = document.getElementById('auto-translate') as HTMLInputElement;
  autoToggle.checked = config.autoTranslate;
  autoToggle.addEventListener('change', async () => {
    await saveConfig({ autoTranslate: autoToggle.checked });
  });

  // 剪贴板翻译
  const clipToggle = document.getElementById('clipboard-translate') as HTMLInputElement;
  clipToggle.checked = false; // 默认关闭
  clipToggle.addEventListener('change', () => {
    sendToActiveTab({ type: 'TOGGLE_CLIPBOARD', enabled: clipToggle.checked });
  });

  // 翻译此页面
  document.getElementById('translate-page')?.addEventListener('click', () => {
    sendToActiveTab({ type: 'TOGGLE_TRANSLATE' });
    window.close();
  });

  // 显示原文
  document.getElementById('restore-page')?.addEventListener('click', () => {
    sendToActiveTab({ type: 'TOGGLE_TRANSLATE' });
    window.close();
  });

  // 视频字幕翻译
  const subtitleBtn = document.getElementById('translate-subtitle') as HTMLButtonElement;
  subtitleBtn?.addEventListener('click', () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'TOGGLE_SUBTITLE' }, (resp) => {
          if (resp?.enabled) {
            subtitleBtn.textContent = '⏹ 关闭字幕翻译';
            subtitleBtn.style.background = '#e74c3c';
            subtitleBtn.style.color = '#fff';
          } else {
            subtitleBtn.textContent = '🎬 翻译视频字幕';
            subtitleBtn.style.background = '';
            subtitleBtn.style.color = '';
          }
        });
      }
    });
  });

  // 语言切换
  langSelect.addEventListener('change', async () => {
    await saveConfig({ targetLang: langSelect.value });
  });

  // 翻译源切换
  providerSelect.addEventListener('change', async () => {
    await saveConfig({ activeProviderId: providerSelect.value });
    updateProviderStatus();
  });

  // 打开设置页
  document.getElementById('open-settings')?.addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
  });
  document.getElementById('open-options')?.addEventListener('click', (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  });

  function updateProviderStatus() {
    const statusEl = document.getElementById('provider-status');
    const active = config.providers.find(p => p.id === config.activeProviderId);
    if (statusEl && active) {
      const needsKey = !['google-free', 'bing-free'].includes(active.type);
      statusEl.textContent = needsKey
        ? `🔑 需要 API Key`
        : `✅ 免费，无需配置`;
    }
  }
}

function sendToActiveTab(msg: any): void {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]?.id) {
      chrome.tabs.sendMessage(tabs[0].id, msg);
    }
  });
}

init();
