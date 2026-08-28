/* ============================================================
   Options — 设置页面逻辑
   ============================================================ */

import { loadConfig, saveConfig } from '../utils/storage';
import { sendMessage } from '../utils/messaging';
import { LANGUAGES } from '../utils/languages';
import { TranslateConfig, ProviderConfig } from '../utils/types';

let config: TranslateConfig;

async function init() {
  config = await loadConfig();

  renderLanguageSelect();
  renderProviders();
  renderBehavior();
  renderStyle();
  renderExcludeSites();
  renderButlerBackend();
  bindEvents();
}

// ---------- 语言 ----------
function renderLanguageSelect() {
  const sel = document.getElementById('target-lang') as HTMLSelectElement;
  for (const lang of LANGUAGES) {
    const opt = document.createElement('option');
    opt.value = lang.code;
    opt.textContent = lang.name;
    if (lang.code === config.targetLang) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.addEventListener('change', () => saveConfig({ targetLang: sel.value }));
}

// ---------- 翻译源 ----------
function renderProviders() {
  const list = document.getElementById('provider-list')!;
  const select = document.getElementById('active-provider') as HTMLSelectElement;

  list.innerHTML = '';
  select.innerHTML = '';

  for (const p of config.providers) {
    // 列表项
    const item = document.createElement('div');
    item.className = `provider-item ${p.id === config.activeProviderId ? 'active' : ''}`;
    const isFree = ['google-free', 'bing-free'].includes(p.type);
    item.innerHTML = `
      <div class="provider-info">
        <div class="provider-name">${p.name}</div>
        <div class="provider-type">
          ${p.type}
          ${isFree ? '<span class="tag tag-free">免费</span>' : '<span class="tag tag-key">需 Key</span>'}
          ${p.model ? ` · ${p.model}` : ''}
        </div>
      </div>
      <div class="provider-actions">
        <button class="btn btn-sm btn-outline" data-action="test" data-id="${p.id}">测试</button>
        <button class="btn btn-sm btn-danger" data-action="delete" data-id="${p.id}">删除</button>
      </div>
    `;
    list.appendChild(item);

    // 下拉选项
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    if (p.id === config.activeProviderId) opt.selected = true;
    select.appendChild(opt);
  }

  select.addEventListener('change', async () => {
    config.activeProviderId = select.value;
    await saveConfig({ activeProviderId: select.value });
    renderProviders();
  });

  // 事件委托
  list.addEventListener('click', async (e) => {
    const btn = e.target as HTMLButtonElement;
    const id = btn.dataset.id;
    if (!id) return;

    if (btn.dataset.action === 'test') {
      const p = config.providers.find(pr => pr.id === id);
      if (p) {
        btn.textContent = '测试中...';
        btn.disabled = true;
        const resp = await sendMessage({ type: 'TEST_PROVIDER', provider: p });
        btn.textContent = resp.type === 'TEST_RESULT' && resp.success ? '✓ 成功' : '✗ 失败';
        setTimeout(() => { btn.textContent = '测试'; btn.disabled = false; }, 2000);
      }
    }

    if (btn.dataset.action === 'delete') {
      if (confirm('确定删除此翻译源？')) {
        config.providers = config.providers.filter(p => p.id !== id);
        if (config.activeProviderId === id && config.providers.length > 0) {
          config.activeProviderId = config.providers[0].id;
        }
        await saveConfig({ providers: config.providers, activeProviderId: config.activeProviderId });
        renderProviders();
      }
    }
  });
}

// ---------- 添加翻译源 ----------
function bindEvents() {
  const addForm = document.getElementById('add-form')!;
  const showBtn = document.getElementById('show-add-form')!;
  const cancelBtn = document.getElementById('cancel-add')!;
  const saveBtn = document.getElementById('save-provider')!;
  const testBtn = document.getElementById('test-provider')!;
  const typeSelect = document.getElementById('new-type') as HTMLSelectElement;

  showBtn.addEventListener('click', () => {
    addForm.style.display = addForm.style.display === 'none' ? 'block' : 'none';
  });
  cancelBtn.addEventListener('click', () => { addForm.style.display = 'none'; });

  // 类型切换时显示/隐藏字段
  typeSelect.addEventListener('change', () => {
    const needKey = !['google-free', 'bing-free', 'butler-bhl'].includes(typeSelect.value);
    document.getElementById('new-key-row')!.style.display = needKey ? 'flex' : 'none';
    document.getElementById('new-endpoint-row')!.style.display =
      ['openai-compat', 'deepl', 'butler-bhl'].includes(typeSelect.value) ? 'flex' : 'none';
    document.getElementById('new-model-row')!.style.display =
      typeSelect.value === 'openai-compat' ? 'flex' : 'none';
  });
  typeSelect.dispatchEvent(new Event('change'));

  // 保存
  saveBtn.addEventListener('click', async () => {
    const provider: ProviderConfig = {
      id: `${typeSelect.value}-${Date.now()}`,
      type: typeSelect.value as any,
      name: (document.getElementById('new-name') as HTMLInputElement).value || typeSelect.value,
      endpoint: (document.getElementById('new-endpoint') as HTMLInputElement).value || undefined,
      apiKey: (document.getElementById('new-key') as HTMLInputElement).value || undefined,
      model: (document.getElementById('new-model') as HTMLInputElement).value || undefined,
      prompt: (document.getElementById('new-prompt') as HTMLInputElement).value || undefined,
      enabled: true,
    };

    config.providers.push(provider);
    await saveConfig({ providers: config.providers });
    addForm.style.display = 'none';
    renderProviders();
    clearAddForm();
  });

  // 测试
  testBtn.addEventListener('click', async () => {
    const resultEl = document.getElementById('test-result')!;
    const provider: ProviderConfig = {
      id: 'test',
      type: typeSelect.value as any,
      name: 'test',
      endpoint: (document.getElementById('new-endpoint') as HTMLInputElement).value || undefined,
      apiKey: (document.getElementById('new-key') as HTMLInputElement).value || undefined,
      model: (document.getElementById('new-model') as HTMLInputElement).value || undefined,
      enabled: true,
    };

    testBtn.textContent = '测试中...';
    testBtn.disabled = true;
    resultEl.className = 'test-result';
    resultEl.style.display = 'none';

    const resp = await sendMessage({ type: 'TEST_PROVIDER', provider });
    if (resp.type === 'TEST_RESULT') {
      resultEl.className = `test-result ${resp.success ? 'success' : 'error'}`;
      resultEl.textContent = resp.message;
      resultEl.style.display = 'block';
    }

    testBtn.textContent = '测试此模型';
    testBtn.disabled = false;
  });

  // 排除网站
  document.getElementById('add-exclude')?.addEventListener('click', async () => {
    const input = document.getElementById('new-exclude') as HTMLInputElement;
    const site = input.value.trim();
    if (site && !config.excludeSites.includes(site)) {
      config.excludeSites.push(site);
      await saveConfig({ excludeSites: config.excludeSites });
      renderExcludeSites();
      input.value = '';
    }
  });

  // 保存所有
  const inputs = document.querySelectorAll('input, select');
  inputs.forEach(input => {
    input.addEventListener('change', saveAll);
  });
}

function clearAddForm() {
  (document.getElementById('new-name') as HTMLInputElement).value = '';
  (document.getElementById('new-endpoint') as HTMLInputElement).value = '';
  (document.getElementById('new-key') as HTMLInputElement).value = '';
  (document.getElementById('new-model') as HTMLInputElement).value = '';
  (document.getElementById('new-prompt') as HTMLInputElement).value = '';
}

// ---------- 翻译行为 ----------
function renderBehavior() {
  (document.getElementById('display-mode') as HTMLSelectElement).value = config.displayMode;
  (document.getElementById('auto-translate') as HTMLInputElement).checked = config.autoTranslate;
  (document.getElementById('trigger-key') as HTMLInputElement).value = config.triggerKey;
  (document.getElementById('input-key') as HTMLInputElement).value = config.inputTranslateKey;
  (document.getElementById('screenshot-key') as HTMLInputElement).value = config.screenshotKey;
}

// ---------- 样式 ----------
function renderStyle() {
  (document.getElementById('theme') as HTMLSelectElement).value = config.theme;
  (document.getElementById('color-follow') as HTMLInputElement).checked = config.colorFollowOriginal;
  (document.getElementById('font-size') as HTMLSelectElement).value = config.fontSize;
}

// ---------- 排除网站 ----------
function renderExcludeSites() {
  const list = document.getElementById('exclude-list')!;
  list.innerHTML = '';
  for (const site of config.excludeSites) {
    const item = document.createElement('span');
    item.className = 'exclude-item';
    item.innerHTML = `${site} <button data-site="${site}">×</button>`;
    list.appendChild(item);
  }
  list.addEventListener('click', async (e) => {
    const btn = e.target as HTMLButtonElement;
    if (btn.dataset.site) {
      config.excludeSites = config.excludeSites.filter(s => s !== btn.dataset.site);
      await saveConfig({ excludeSites: config.excludeSites });
      renderExcludeSites();
    }
  });
}

// ---------- Butler 后端 ----------
function renderButlerBackend() {
  (document.getElementById('butler-url') as HTMLInputElement).value = config.butlerBackendUrl;
}

// ---------- 全局保存 ----------
async function saveAll() {
  await saveConfig({
    displayMode: (document.getElementById('display-mode') as HTMLSelectElement).value as any,
    autoTranslate: (document.getElementById('auto-translate') as HTMLInputElement).checked,
    triggerKey: (document.getElementById('trigger-key') as HTMLInputElement).value,
    inputTranslateKey: (document.getElementById('input-key') as HTMLInputElement).value,
    screenshotKey: (document.getElementById('screenshot-key') as HTMLInputElement).value,
    theme: (document.getElementById('theme') as HTMLSelectElement).value as any,
    colorFollowOriginal: (document.getElementById('color-follow') as HTMLInputElement).checked,
    fontSize: (document.getElementById('font-size') as HTMLSelectElement).value,
    butlerBackendUrl: (document.getElementById('butler-url') as HTMLInputElement).value,
  });
}

init();
