/* ============================================================
   Options — 设置页面逻辑
   ============================================================ */

import { loadConfig, saveConfig } from '../utils/storage';
import { sendMessage } from '../utils/messaging';
import { LANGUAGES } from '../utils/languages';
import { TranslateConfig, ProviderConfig, PresetTemplate, SitePresetBinding } from '../utils/types';
import { mergePresets, BUILTIN_PRESETS } from '../utils/presets';
import { parseCustomRules, serializeCustomRules, getBuiltinRules } from '../content/dom/site-rules';

let config: TranslateConfig;

async function init() {
  config = await loadConfig();
  // 预设合并内置（用户同 id 覆盖）
  config.presets = mergePresets(config.presets);

  renderLanguageSelect();
  renderProviders();
  renderBehavior();
  renderStyle();
  renderPresets();
  renderCustomRules();
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
  const testBtn = document.getElementById('test-provider') as HTMLButtonElement;
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

  // 预设编辑器 / 站点绑定 / 术语同步
  bindPresetEditor();
  renderGlossarySync();
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
  (document.getElementById('bilingual-layout') as HTMLSelectElement).value = config.bilingualLayout || 'columns';
  (document.getElementById('auto-translate') as HTMLInputElement).checked = config.autoTranslate;
  (document.getElementById('trigger-key') as HTMLInputElement).value = config.triggerKey;
  (document.getElementById('input-key') as HTMLInputElement).value = config.inputTranslateKey;
  (document.getElementById('screenshot-key') as HTMLInputElement).value = config.screenshotKey;
  (document.getElementById('hover-trigger-key') as HTMLInputElement).value = config.hoverTriggerKey || 'Alt';
  (document.getElementById('input-triple-space') as HTMLInputElement).checked = config.inputTripleSpace !== false;
  (document.getElementById('input-direction') as HTMLSelectElement).value = config.inputDirection || 'auto';
  (document.getElementById('ctx-enabled') as HTMLInputElement).checked = config.ctxEnabled !== false;
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
    bilingualLayout: (document.getElementById('bilingual-layout') as HTMLSelectElement).value as any,
    autoTranslate: (document.getElementById('auto-translate') as HTMLInputElement).checked,
    triggerKey: (document.getElementById('trigger-key') as HTMLInputElement).value,
    inputTranslateKey: (document.getElementById('input-key') as HTMLInputElement).value,
    screenshotKey: (document.getElementById('screenshot-key') as HTMLInputElement).value,
    hoverTriggerKey: (document.getElementById('hover-trigger-key') as HTMLInputElement).value || 'Alt',
    inputTripleSpace: (document.getElementById('input-triple-space') as HTMLInputElement).checked,
    inputDirection: (document.getElementById('input-direction') as HTMLSelectElement).value as any,
    ctxEnabled: (document.getElementById('ctx-enabled') as HTMLInputElement).checked,
    theme: (document.getElementById('theme') as HTMLSelectElement).value as any,
    colorFollowOriginal: (document.getElementById('color-follow') as HTMLInputElement).checked,
    fontSize: (document.getElementById('font-size') as HTMLSelectElement).value,
    butlerBackendUrl: (document.getElementById('butler-url') as HTMLInputElement).value,
  });
}

// ---------- AI 专家 / 行业身份预设 ----------
function renderPresets() {
  const presets = config.presets || BUILTIN_PRESETS;

  // 当前预设下拉
  const select = document.getElementById('preset-select') as HTMLSelectElement;
  select.innerHTML = '';
  for (const p of presets) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name + (p.builtin ? '（内置）' : '');
    if (p.id === config.activePresetId) opt.selected = true;
    select.appendChild(opt);
  }
  select.onchange = async () => {
    config.activePresetId = select.value;
    await saveConfig({ activePresetId: select.value });
  };

  // 绑定下拉（站点绑定用）
  const bindingPreset = document.getElementById('binding-preset') as HTMLSelectElement;
  bindingPreset.innerHTML = '';
  for (const p of presets) {
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    bindingPreset.appendChild(opt);
  }

  // 预设列表
  const list = document.getElementById('preset-list')!;
  list.innerHTML = '';
  for (const p of presets) {
    const item = document.createElement('div');
    item.className = 'provider-item';
    item.innerHTML = `
      <div class="provider-info">
        <div class="provider-name">${p.name}${p.builtin ? ' <span class="tag tag-free">内置</span>' : ''}</div>
        <div class="provider-type">${p.identity}</div>
      </div>
      <div class="provider-actions">
        <button class="btn btn-sm btn-outline" data-preset-edit="${p.id}">编辑</button>
      </div>
    `;
    list.appendChild(item);
  }
  list.onclick = (e) => {
    const btn = e.target as HTMLElement;
    const id = btn.dataset.presetEdit;
    if (id) openPresetEditor(id);
  };

  renderBindings();
}

function openPresetEditor(id: string) {
  const preset = (config.presets || []).find(p => p.id === id);
  if (!preset) return;
  const editor = document.getElementById('preset-editor')!;
  editor.style.display = 'block';
  (document.getElementById('preset-edit-id') as HTMLInputElement).value = preset.id;
  (document.getElementById('preset-edit-name') as HTMLInputElement).value = preset.name;
  (document.getElementById('preset-edit-identity') as HTMLInputElement).value = preset.identity;
  (document.getElementById('preset-edit-tone') as HTMLInputElement).value = preset.tone;
  (document.getElementById('preset-edit-termstyle') as HTMLInputElement).value = preset.termStyle;
  (document.getElementById('preset-edit-numbers') as HTMLInputElement).value = preset.rules.numbers;
  (document.getElementById('preset-edit-units') as HTMLInputElement).value = preset.rules.units;
  (document.getElementById('preset-edit-code') as HTMLInputElement).value = preset.rules.code;
}

function bindPresetEditor() {
  document.getElementById('preset-new')?.addEventListener('click', () => {
    const id = `custom-${Date.now()}`;
    const preset: PresetTemplate = {
      id,
      name: '自定义预设',
      identity: '你是一名专业译员。',
      tone: '中性、自然',
      termStyle: '常用译法',
      rules: { numbers: '数字保留原样', units: '单位保留国际符号', code: '代码不翻译' },
    };
    config.presets = mergePresets([...(config.presets || []), preset]);
    void saveConfig({ presets: config.presets });
    renderPresets();
    openPresetEditor(id);
  });

  document.getElementById('preset-cancel')?.addEventListener('click', () => {
    (document.getElementById('preset-editor') as HTMLElement).style.display = 'none';
  });

  document.getElementById('preset-save')?.addEventListener('click', async () => {
    const id = (document.getElementById('preset-edit-id') as HTMLInputElement).value;
    const preset = (config.presets || []).find(p => p.id === id);
    if (!preset) return;
    preset.name = (document.getElementById('preset-edit-name') as HTMLInputElement).value || preset.name;
    preset.identity = (document.getElementById('preset-edit-identity') as HTMLInputElement).value;
    preset.tone = (document.getElementById('preset-edit-tone') as HTMLInputElement).value;
    preset.termStyle = (document.getElementById('preset-edit-termstyle') as HTMLInputElement).value;
    preset.rules = {
      numbers: (document.getElementById('preset-edit-numbers') as HTMLInputElement).value,
      units: (document.getElementById('preset-edit-units') as HTMLInputElement).value,
      code: (document.getElementById('preset-edit-code') as HTMLInputElement).value,
    };
    await saveConfig({ presets: config.presets });
    renderPresets();
  });

  document.getElementById('preset-delete')?.addEventListener('click', async () => {
    const id = (document.getElementById('preset-edit-id') as HTMLInputElement).value;
    const preset = (config.presets || []).find(p => p.id === id);
    if (!preset) return;
    if (preset.builtin) {
      alert('内置预设不可删除（可以编辑其内容）');
      return;
    }
    if (!confirm(`确定删除预设「${preset.name}」？`)) return;
    config.presets = (config.presets || []).filter(p => p.id !== id);
    config.sitePresetBindings = (config.sitePresetBindings || []).filter(b => b.presetId !== id);
    await saveConfig({ presets: config.presets, sitePresetBindings: config.sitePresetBindings });
    (document.getElementById('preset-editor') as HTMLElement).style.display = 'none';
    renderPresets();
  });

  document.getElementById('binding-add')?.addEventListener('click', async () => {
    const pattern = (document.getElementById('binding-pattern') as HTMLInputElement).value.trim();
    const presetId = (document.getElementById('binding-preset') as HTMLSelectElement).value;
    if (!pattern) return;
    config.sitePresetBindings = config.sitePresetBindings || [];
    config.sitePresetBindings.push({ pattern, presetId });
    await saveConfig({ sitePresetBindings: config.sitePresetBindings });
    (document.getElementById('binding-pattern') as HTMLInputElement).value = '';
    renderBindings();
  });
}

function renderBindings() {
  const container = document.getElementById('preset-bindings');
  if (!container) return;
  container.innerHTML = '';
  for (const b of config.sitePresetBindings || []) {
    const preset = (config.presets || []).find(p => p.id === b.presetId);
    const item = document.createElement('span');
    item.className = 'exclude-item';
    item.innerHTML = `${b.pattern} → ${preset?.name || b.presetId} <button data-binding="${b.pattern}">×</button>`;
    container.appendChild(item);
  }
  container.onclick = async (e) => {
    const btn = e.target as HTMLElement;
    const pattern = btn.dataset.binding;
    if (pattern) {
      config.sitePresetBindings = (config.sitePresetBindings || []).filter(b => b.pattern !== pattern);
      await saveConfig({ sitePresetBindings: config.sitePresetBindings });
      renderBindings();
    }
  };
}

// ---------- 自定义站点规则（导入 / 导出） ----------
function renderCustomRules() {
  const ta = document.getElementById('custom-rules-json') as HTMLTextAreaElement;
  ta.value = JSON.stringify(config.customSiteRules || [], null, 2);
  const status = document.getElementById('rules-status')!;

  document.getElementById('rules-save')?.addEventListener('click', async () => {
    const { rules, error } = parseCustomRules(ta.value);
    if (rules.length === 0 && error) {
      status.textContent = `⚠️ ${error}`;
      status.style.color = '#b3261e';
      return;
    }
    config.customSiteRules = rules;
    await saveConfig({ customSiteRules: rules });
    status.textContent = error ? `已保存 ${rules.length} 条（${error}）` : `✅ 已保存 ${rules.length} 条自定义规则`;
    status.style.color = error ? '#856404' : '#155724';
  });

  document.getElementById('rules-export')?.addEventListener('click', () => {
    const json = serializeCustomRules(config.customSiteRules || []);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'butler-site-rules.json';
    a.click();
    URL.revokeObjectURL(url);
    status.textContent = `已导出 ${(config.customSiteRules || []).length} 条自定义规则（内置规则可通过 ${getBuiltinRules().length} 条内置表查看）`;
    status.style.color = '#155724';
  });

  document.getElementById('rules-import')?.addEventListener('click', () => {
    (document.getElementById('rules-file') as HTMLInputElement).click();
  });

  (document.getElementById('rules-file') as HTMLInputElement)?.addEventListener('change', async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    const text = await file.text();
    const { rules, error } = parseCustomRules(text);
    if (rules.length === 0 && error) {
      status.textContent = `⚠️ 导入失败：${error}`;
      status.style.color = '#b3261e';
      return;
    }
    config.customSiteRules = rules;
    await saveConfig({ customSiteRules: rules });
    ta.value = JSON.stringify(rules, null, 2);
    status.textContent = error ? `已导入 ${rules.length} 条（${error}）` : `✅ 已导入 ${rules.length} 条自定义规则`;
    status.style.color = error ? '#856404' : '#155724';
  });
}

// ---------- 术语表与 Butler 后端同步 ----------
function renderGlossarySync() {
  const status = document.getElementById('glossary-sync-status')!;
  document.getElementById('glossary-push')?.addEventListener('click', async () => {
    status.textContent = '推送中...';
    const resp = await sendMessage({ type: 'SYNC_GLOSSARY_PUSH' });
    status.textContent = resp.type === 'ACTION_RESULT' ? resp.message : '未知错误';
  });
  document.getElementById('glossary-pull')?.addEventListener('click', async () => {
    status.textContent = '拉取中...';
    const resp = await sendMessage({ type: 'SYNC_GLOSSARY_PULL' });
    status.textContent = resp.type === 'ACTION_RESULT' ? resp.message : '未知错误';
  });

  // 双语导出面板（在当前标签页打开）
  document.getElementById('open-export-panel')?.addEventListener('click', () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'SHOW_EXPORT_PANEL' }, () => {
          if (chrome.runtime.lastError) {
            alert('无法在当前标签页打开导出面板（部分特殊页面如 chrome:// 不支持内容脚本）');
          }
        });
      }
    });
  });
}

init();
