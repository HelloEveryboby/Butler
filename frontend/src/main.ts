/**
 * Butler — Adaptive Canvas Frontend
 * Single self-contained module: UI interactions + pywebview bridge contract.
 */

interface Window {
  pywebview?: { api: any };
  Terminal?: any;
  FitAddon?: any;
  marked?: any;
  DOMPurify?: any;
  [key: string]: any;
}

const api = (): any => (window.pywebview && window.pywebview.api) || null;
const hasApi = (): boolean => !!api();

// ─── Helpers ───────────────────────────────────────────────
function $(id: string): HTMLElement | null { return document.getElementById(id); }
function el(tag: string, cls?: string, html?: string): HTMLElement {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}
function escapeHtml(s: string): string {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
function renderMarkdown(text: string): string {
  try {
    if (window.marked && window.DOMPurify) {
      return window.DOMPurify.sanitize(window.marked.parse(text));
    }
  } catch (_) { /* ignore */ }
  return escapeHtml(text).replace(/\n/g, '<br>');
}

// ─── Toast & Notifications ─────────────────────────────────
function showToast(msg: string, type: 'success' | 'error' | 'info' = 'info'): void {
  const c = $('toast-container');
  if (!c) return;
  const t = el('div', `toast ${type}`, escapeHtml(msg));
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateY(10px)'; setTimeout(() => t.remove(), 200); }, 2600);
}

function pushNotification(title: string, message: string, type: 'info' | 'success' | 'error' = 'info'): void {
  const c = $('notification-container');
  if (!c) return;
  const n = el('div', `notif ${type}`);
  n.innerHTML = `<div class="n-title">${escapeHtml(title)}</div><div class="n-msg">${escapeHtml(message)}</div>`;
  n.onclick = () => n.remove();
  c.appendChild(n);
  setTimeout(() => { n.style.opacity = '0'; n.style.transform = 'translateX(20px)'; setTimeout(() => n.remove(), 250); }, 6000);
}
(window as any).showToast = showToast;
(window as any).pushNotification = pushNotification;

// ─── Navigation ────────────────────────────────────────────
const views = ['chat', 'dag', 'history', 'skills'];
function switchView(v: string): void {
  document.querySelectorAll('.rail-item[data-view]').forEach((i) =>
    i.classList.toggle('active', (i as HTMLElement).dataset.view === v));
  views.forEach((name) => {
    const node = $('view-' + name);
    if (node) node.classList.toggle('active', name === v);
  });
  if (v === 'dag') renderDag();
  if (v === 'skills') loadSkills();
  if (v === 'history') loadTimeMachine();
}
(window as any).switchView = switchView;

document.querySelectorAll('.rail-item[data-view]').forEach((item) => {
  item.addEventListener('click', () => switchView((item as HTMLElement).dataset.view || 'chat'));
});

// ─── Inspector ─────────────────────────────────────────────
function toggleInspector(): void {
  $('main')?.classList.toggle('inspector-collapsed');
}
(window as any).toggleInspector = toggleInspector;
$('toggleInspector')?.addEventListener('click', toggleInspector);

// ─── Command Palette ───────────────────────────────────────
const commands: { g: string; n: string; s: string; k: string; a: () => void }[] = [
  { g: '导航', n: '对话', s: '智能助手', k: '⌘1', a: () => switchView('chat') },
  { g: '导航', n: '任务画布', s: 'DAG 流水线', k: '⌘2', a: () => switchView('dag') },
  { g: '导航', n: '时光机', s: '历史回溯', k: '⌘3', a: () => switchView('history') },
  { g: '导航', n: '技能仓储', s: '管理技能', k: '⌘4', a: () => switchView('skills') },
  { g: '操作', n: '系统自检与安全审计', s: '扫描安全配置与开放端口', k: '↵', a: () => runQuick('系统自检与安全审计') },
  { g: '操作', n: '一键清理系统垃圾', s: '清除冗余缓存', k: '↵', a: () => runQuick('一键清理系统垃圾') },
  { g: '操作', n: '开启局域网同步', s: '同步到局域网节点', k: '↵', a: () => runQuick('开启局域网同步') },
  { g: '操作', n: '本地 FFT 音频降噪', s: 'C++ 音频算法', k: '↵', a: () => runQuick('本地 FFT 音频降噪') },
  { g: '操作', n: '打开设置', s: '系统配置中心', k: '⌘,', a: () => toggleSettings() },
  { g: '操作', n: '打开终端', s: 'PTY 终端会话', k: '⌘`', a: () => toggleTerminal() },
];

function renderPalette(filter = ''): void {
  const list = $('paletteList');
  if (!list) return;
  const f = filter.toLowerCase();
  const groups: Record<string, typeof commands> = {};
  commands.forEach((c) => {
    if (!f || c.n.toLowerCase().includes(f) || c.s.toLowerCase().includes(f)) {
      (groups[c.g] = groups[c.g] || []).push(c);
    }
  });
  list.innerHTML = Object.entries(groups).map(([g, items]) =>
    `<div class="palette-group-title">${g}</div>` +
    items.map((c, i) => `
      <div class="palette-item ${i === 0 ? 'sel' : ''}" data-idx="${commands.indexOf(c)}">
        <div class="pi-icon">${g === '导航' ? '▸' : '⚡'}</div>
        <div class="pi-text"><div class="pi-name">${c.n}</div><div class="pi-sub">${c.s}</div></div>
        <span class="pi-short">${c.k}</span>
      </div>`).join('')
  ).join('');
  list.querySelectorAll('.palette-item').forEach((node) => {
    node.addEventListener('click', () => {
      const idx = parseInt((node as HTMLElement).dataset.idx || '-1', 10);
      closePalette();
      if (commands[idx]) commands[idx].a();
    });
  });
}

function openPalette(): void {
  const p = $('palette');
  const inp = $('paletteInput') as HTMLInputElement | null;
  if (!p) return;
  p.classList.add('show');
  if (inp) { inp.value = ''; inp.focus(); }
  renderPalette();
}
function closePalette(): void { $('palette')?.classList.remove('show'); }
function filterPalette(v: string): void { renderPalette(v); }
(window as any).openPalette = openPalette;
(window as any).closePalette = closePalette;
(window as any).filterPalette = filterPalette;

$('cmdBar')?.addEventListener('click', openPalette);
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); }
  if (e.key === 'Escape') closePalette();
});

// ─── Chat ──────────────────────────────────────────────────
let currentStreamId: string | null = null;

function sendMessage(): void {
  const input = $('composerInput') as HTMLTextAreaElement | null;
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  const msgs = $('messages');
  if (!msgs) return;

  const userMsg = el('div', 'msg user');
  userMsg.innerHTML = `<div class="avatar">我</div><div class="bubble">${escapeHtml(text)}</div>`;
  msgs.appendChild(userMsg);
  input.value = '';

  currentStreamId = 'r' + Date.now();
  const aiMsg = el('div', 'msg ai');
  aiMsg.id = currentStreamId;
  aiMsg.innerHTML = `<div class="avatar">B</div><div class="bubble"><span class="typing"><span></span><span></span><span></span></span></div>`;
  msgs.appendChild(aiMsg);
  msgs.scrollTop = msgs.scrollHeight;

  if (hasApi()) {
    api().handle_command(text);
  } else {
    // mock reply
    setTimeout(() => {
      const b = aiMsg.querySelector('.bubble');
      if (b) b.innerHTML = `已收到：<code>${escapeHtml(text)}</code><br>（无后端连接，演示模式）`;
      msgs.scrollTop = msgs.scrollHeight;
    }, 900);
  }
}
(window as any).sendMessage = sendMessage;

function runQuick(cmd: string): void {
  switchView('chat');
  const input = $('composerInput') as HTMLTextAreaElement | null;
  if (input) input.value = cmd;
  sendMessage();
}
(window as any).runQuick = runQuick;
(window as any).triggerQuickAction = (cmd: string) => runQuick(cmd);

const composerInput = $('composerInput') as HTMLTextAreaElement | null;
composerInput?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

// ─── DAG Canvas ────────────────────────────────────────────
interface DagNode { id: number; x: number; y: number; icon: string; name: string; meta: string; }
let dagNodes: DagNode[] = [
  { id: 1, x: 60, y: 60, icon: '📄', name: 'DOCX 读取', meta: 'docx_read' },
  { id: 2, x: 300, y: 60, icon: '🔄', name: '转 Markdown', meta: 'markitdown' },
  { id: 3, x: 540, y: 60, icon: '🌐', name: '翻译', meta: 'translate -> EN' },
  { id: 4, x: 300, y: 220, icon: '💾', name: '归档输出', meta: 'archive_compress' },
];
let dagEdges: [number, number][] = [[1, 2], [2, 3], [2, 4]];

function renderDag(): void {
  const canvas = $('dagCanvas');
  if (!canvas) return;
  canvas.querySelectorAll('.dag-node').forEach((n) => n.remove());
  dagNodes.forEach((nd) => {
    const el2 = el('div', 'dag-node');
    el2.style.left = nd.x + 'px';
    el2.style.top = nd.y + 'px';
    el2.dataset.id = String(nd.id);
    el2.innerHTML = `<span class="port in"></span>
      <div class="node-head"><div class="node-icon">${nd.icon}</div>${nd.name}</div>
      <div class="node-meta">${nd.meta}</div>
      <span class="port out"></span>`;
    makeDraggable(el2, nd);
    canvas.appendChild(el2);
  });
  drawEdges();
}

function drawEdges(): void {
  const svg = $('dagSvg') as unknown as SVGSVGElement | null;
  const canvas = $('dagCanvas');
  if (!svg || !canvas) return;
  const ns = 'http://www.w3.org/2000/svg';
  svg.innerHTML = '';
  svg.setAttribute('width', String(canvas.scrollWidth));
  svg.setAttribute('height', String(canvas.scrollHeight));
  dagEdges.forEach(([a, b]) => {
    const na = dagNodes.find((n) => n.id === a);
    const nb = dagNodes.find((n) => n.id === b);
    if (!na || !nb) return;
    const x1 = na.x + 170, y1 = na.y + 24;
    const x2 = nb.x, y2 = nb.y + 24;
    const mx = (x1 + x2) / 2;
    const path = document.createElementNS(ns, 'path');
    path.setAttribute('d', `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`);
    path.setAttribute('stroke', '#E8A04F');
    path.setAttribute('stroke-opacity', '0.5');
    path.setAttribute('stroke-width', '1.5');
    path.setAttribute('fill', 'none');
    svg.appendChild(path);
  });
}

function makeDraggable(el2: HTMLElement, nd: DagNode): void {
  let sx = 0, sy = 0, ox = 0, oy = 0, dragging = false;
  el2.addEventListener('mousedown', (e) => {
    dragging = true; el2.classList.add('dragging');
    sx = e.clientX; sy = e.clientY; ox = nd.x; oy = nd.y;
    e.preventDefault();
  });
  const mm = (e: MouseEvent) => {
    if (!dragging) return;
    nd.x = ox + (e.clientX - sx);
    nd.y = oy + (e.clientY - sy);
    el2.style.left = nd.x + 'px';
    el2.style.top = nd.y + 'px';
    drawEdges();
  };
  const mu = () => { if (dragging) { dragging = false; el2.classList.remove('dragging'); } };
  document.addEventListener('mousemove', mm);
  document.addEventListener('mouseup', mu);
}

function toggleRunDag(): void {
  document.querySelectorAll('.dag-node').forEach((n) => n.classList.add('running'));
  setTimeout(() => document.querySelectorAll('.dag-node').forEach((n) => n.classList.remove('running')), 2500);
}
function clearDag(): void { dagEdges = []; drawEdges(); }
(window as any).toggleRunDag = toggleRunDag;
(window as any).clearDag = clearDag;

// ─── Time Machine ──────────────────────────────────────────
async function loadTimeMachine(): Promise<void> {
  const tl = $('timeline');
  if (!tl) return;
  if (hasApi()) {
    try {
      const now = Date.now() / 1000;
      const data = await api().get_time_machine_range(now - 86400, now);
      if (Array.isArray(data) && data.length) {
        tl.innerHTML = data.slice(0, 40).map((r: any) => {
          const t = r.timestamp ? new Date(r.timestamp * 1000).toLocaleTimeString() : '';
          return `<div class="tl-item ${r.level === 'error' ? 'error' : r.level === 'success' ? 'success' : ''}">
            <div class="tl-time">${t}</div>
            <div class="tl-title">${escapeHtml(r.title || r.event || '')}</div>
            <div class="tl-desc">${escapeHtml(r.message || r.desc || '')}</div>
          </div>`;
        }).join('');
        return;
      }
    } catch (e) { /* fall through to demo */ }
  }
  // demo data
  tl.innerHTML = `
    <div class="tl-item success"><div class="tl-time">10:42:18</div><div class="tl-title">系统自检完成</div><div class="tl-desc">扫描 247 项配置，发现 3 个可优化项。</div><span class="tl-tag">security_audit</span></div>
    <div class="tl-item"><div class="tl-time">10:38:02</div><div class="tl-title">DAG 流水线执行</div><div class="tl-desc">docx → markdown → translate，3 节点串行，耗时 8.2s。</div><span class="tl-tag">pipeline</span></div>
    <div class="tl-item error"><div class="tl-time">10:21:55</div><div class="tl-title">端口 8080 被占用</div><div class="tl-desc">process pid=3421 占用端口，已提示处理。</div><span class="tl-tag">error</span></div>
    <div class="tl-item success"><div class="tl-time">09:30:00</div><div class="tl-title">Butler 启动</div><div class="tl-desc">所有子系统就绪。</div><span class="tl-tag">lifecycle</span></div>`;
}
(window as any).loadTimeMachine = loadTimeMachine;

// ─── Skills ────────────────────────────────────────────────
let allSkills: any[] = [];
async function loadSkills(): Promise<void> {
  const grid = $('skillsGrid');
  if (!grid) return;
  if (hasApi()) {
    try {
      const raw = await api().get_skills_list();
      // raw may be a markdown string; try to parse or display
      if (typeof raw === 'string') {
        grid.innerHTML = `<pre style="color:var(--text-dim);white-space:pre-wrap;font-family:var(--mono);font-size:12px">${escapeHtml(raw)}</pre>`;
        return;
      }
      allSkills = Array.isArray(raw) ? raw : [];
    } catch (_) { allSkills = []; }
  }
  if (!allSkills.length) {
    allSkills = [
      { name: 'markitdown', ver: 'v2.1', desc: 'PDF/DOCX/PPTX 转 Markdown', on: true, icon: '📄', color: '#E8A04F' },
      { name: 'archive_manager', ver: 'v1.4', desc: '压缩/解压/加密打包', on: true, icon: '📦', color: '#5EEAD4' },
      { name: 'sec_scan', ver: 'v3.0', desc: '端口扫描与安全审计', on: true, icon: '🛡', color: '#FB7185' },
      { name: 'storage_hub', ver: 'v2.2', desc: 'OneDrive/WebDAV/百度云', on: false, icon: '☁', color: '#007AFF' },
      { name: 'format_convert', ver: 'v1.2', desc: '文档格式互转', on: true, icon: '🔄', color: '#34C759' },
      { name: 'sys_cleaner', ver: 'v2.0', desc: '系统垃圾清理', on: true, icon: '🧹', color: '#FF9500' },
    ];
  }
  renderSkills(allSkills);
}

function renderSkills(list: any[]): void {
  const grid = $('skillsGrid');
  if (!grid) return;
  grid.innerHTML = list.map((s) => {
    const color = s.color || '#E8A04F';
    return `<div class="skill-card" onclick="runSkill('${escapeHtml(s.name)}')">
      <div class="sc-head">
        <div class="sc-icon" style="background:${color}22;color:${color}">${s.icon || '🧩'}</div>
        <div><div class="sc-name">${escapeHtml(s.name)}</div><div class="sc-ver">${s.ver || ''}</div></div>
      </div>
      <div class="sc-desc">${escapeHtml(s.desc || '')}</div>
      <div class="sc-foot"><span class="sc-badge ${s.on ? 'on' : 'off'}">${s.on ? '已启用' : '已禁用'}</span><span style="font-size:11px;color:var(--text-mute)">→</span></div>
    </div>`;
  }).join('');
}

function filterSkills(q: string): void {
  const f = q.toLowerCase();
  renderSkills(allSkills.filter((s) => !f || (s.name || '').toLowerCase().includes(f) || (s.desc || '').toLowerCase().includes(f)));
}
function runSkill(name: string): void {
  runQuick(name);
}
(window as any).filterSkills = filterSkills;
(window as any).runSkill = runSkill;

// ─── Settings ──────────────────────────────────────────────
function toggleSettings(): void {
  const o = $('settings-overlay');
  if (!o) return;
  o.classList.toggle('hidden');
  if (!o.classList.contains('hidden')) loadModelConfig();
}
function switchSettingsTab(tab: string): void {
  document.querySelectorAll('.settings-tab').forEach((t) => t.classList.toggle('active', (t as HTMLElement).dataset.tab === tab));
  document.querySelectorAll('.settings-pane').forEach((p) => p.classList.toggle('active', p.id === 'pane-' + tab));
  if (tab === 'all') loadAllConfig();
  if (tab === 'quota') loadQuota();
}
(window as any).toggleSettings = toggleSettings;
(window as any).switchSettingsTab = switchSettingsTab;

async function loadModelConfig(): Promise<void> {
  if (!hasApi()) return;
  try {
    const c = await api().get_model_config();
    ($('setting-provider') as HTMLSelectElement).value = c.provider || 'deepseek';
    ($('setting-base-url') as HTMLInputElement).value = c.base_url || '';
    ($('setting-model-name') as HTMLInputElement).value = c.model_name || '';
    ($('setting-api-key') as HTMLInputElement).value = c.api_key_set ? (c.api_key || '••••') : '';
    ($('setting-provider-label') as HTMLInputElement).value = c.provider_label || '';
    ($('setting-temperature') as HTMLInputElement).value = String(c.temperature ?? 0.7);
    ($('temp-val') as HTMLElement).textContent = String(c.temperature ?? 0.7);
    ($('setting-max-tokens') as HTMLInputElement).value = String(c.max_tokens ?? 4096);
    onProviderChange();
    const mn = $('modelName'); if (mn) mn.textContent = c.model_name || 'deepseek-chat';
    const sb = $('sbModel'); if (sb) sb.textContent = c.model_name || 'deepseek-chat';
  } catch (e) { /* ignore */ }
}

function onProviderChange(): void {
  const p = ($('setting-provider') as HTMLSelectElement).value;
  document.querySelector('.field-custom-label')?.classList.toggle('hidden', p !== 'custom');
  document.querySelector('.field-secret-key')?.classList.toggle('hidden', p !== 'baidu' && p !== 'qianfan');
}
function toggleApiKeyVisibility(): void {
  const inp = $('setting-api-key') as HTMLInputElement;
  if (inp) inp.type = inp.type === 'password' ? 'text' : 'password';
}
(window as any).onProviderChange = onProviderChange;
(window as any).toggleApiKeyVisibility = toggleApiKeyVisibility;

async function testModelConnection(): Promise<void> {
  const badge = $('model-status-badge');
  if (!hasApi()) { if (badge) { badge.className = 'badge error'; badge.textContent = '无后端'; } return; }
  if (badge) { badge.className = 'badge idle'; badge.textContent = '测试中…'; }
  try {
    const cfg = {
      provider: ($('setting-provider') as HTMLSelectElement).value,
      api_key: ($('setting-api-key') as HTMLInputElement).value,
      base_url: ($('setting-base-url') as HTMLInputElement).value,
      model_name: ($('setting-model-name') as HTMLInputElement).value,
      secret_key: ($('setting-secret-key') as HTMLInputElement).value,
      temperature: parseFloat(($('setting-temperature') as HTMLInputElement).value),
      max_tokens: parseInt(($('setting-max-tokens') as HTMLInputElement).value, 10),
    };
    const r = await api().test_model_connection(cfg);
    if (badge) {
      if (r && r.success) { badge.className = 'badge success'; badge.textContent = `✓ ${r.latency_ms || ''}ms`.trim(); }
      else { badge.className = 'badge error'; badge.textContent = '✗ 失败'; }
    }
  } catch (e) {
    if (badge) { badge.className = 'badge error'; badge.textContent = '✗ 异常'; }
  }
}

async function saveModelSettings(): Promise<void> {
  if (!hasApi()) { showToast('无后端连接', 'error'); return; }
  try {
    await api().save_model_config({
      provider: ($('setting-provider') as HTMLSelectElement).value,
      api_key: ($('setting-api-key') as HTMLInputElement).value,
      base_url: ($('setting-base-url') as HTMLInputElement).value,
      model_name: ($('setting-model-name') as HTMLInputElement).value,
      provider_label: ($('setting-provider-label') as HTMLInputElement).value,
      secret_key: ($('setting-secret-key') as HTMLInputElement).value,
      temperature: parseFloat(($('setting-temperature') as HTMLInputElement).value),
      max_tokens: parseInt(($('setting-max-tokens') as HTMLInputElement).value, 10),
    });
    showToast('模型配置已保存并生效', 'success');
    loadModelConfig();
  } catch (e) {
    showToast('保存失败: ' + String(e), 'error');
  }
}
(window as any).testModelConnection = testModelConnection;
(window as any).saveModelSettings = saveModelSettings;

async function loadAllConfig(): Promise<void> {
  const c = $('all-config-container');
  const st = $('all-config-status');
  if (!c) return;
  if (!hasApi()) { if (st) st.textContent = '无后端连接'; return; }
  try {
    const cfg = await api().get_all_config();
    const entries = Object.entries(cfg || {});
    if (st) st.textContent = `共 ${entries.length} 项配置`;
    c.innerHTML = entries.map(([k, v]: [string, any]) => {
      const val = v && typeof v === 'object' ? v.value : v;
      const sens = v && typeof v === 'object' ? v.sensitive : false;
      return `<div class="config-item">
        <span class="ck">${escapeHtml(k)}</span>
        <input data-key="${escapeHtml(k)}" data-sensitive="${sens ? '1' : '0'}" value="${escapeHtml(String(val ?? ''))}">
      </div>`;
    }).join('');
  } catch (e) {
    if (st) st.textContent = '加载失败';
  }
}

async function saveAllConfig(): Promise<void> {
  if (!hasApi()) { showToast('无后端连接', 'error'); return; }
  const inputs = document.querySelectorAll<HTMLInputElement>('#all-config-container input');
  const data: Record<string, any> = {};
  inputs.forEach((inp) => { data[inp.dataset.key || ''] = inp.value; });
  try {
    const r = await api().save_all_config(data);
    showToast(r?.message || '配置已保存', 'success');
  } catch (e) {
    showToast('保存失败', 'error');
  }
}
(window as any).saveAllConfig = saveAllConfig;

async function loadQuota(): Promise<void> {
  const c = $('quota-container');
  if (!c) return;
  if (!hasApi()) { c.textContent = '无后端连接'; return; }
  try {
    const r = await api().get_quota_report();
    const items = r?.items || [];
    c.innerHTML = items.map((it: any) => `
      <div class="stat-row"><span class="k">${escapeHtml(it.name)}</span><span class="v">${it.used} / ${it.total}</span></div>
      <div class="meter"><div style="width:${Math.min(100, (it.used / it.total) * 100)}%;background:var(--amber)"></div></div>`).join('') || '<div style="color:var(--text-mute)">暂无额度数据</div>';
  } catch (e) { c.textContent = '加载失败'; }
}

async function onVoiceEngineChange(): Promise<void> {
  const eng = ($('setting-voice-engine') as HTMLSelectElement).value;
  if (hasApi()) {
    try { await api().set_voice_engine(eng); } catch (_) { /* ignore */ }
  }
  const st = $('voice-engine-status');
  if (st) st.textContent = `已切换至: ${eng}`;
}
(window as any).onVoiceEngineChange = onVoiceEngineChange;

// ─── Terminal (xterm.js) ───────────────────────────────────
let term: any = null;
let termStarted = false;

function toggleTerminal(): void {
  const o = $('terminal-overlay');
  if (!o) return;
  const hidden = o.classList.contains('hidden');
  o.classList.toggle('hidden');
  if (hidden) {
    if (!term) initTerminal();
    if (!termStarted && hasApi()) {
      api().start_terminal();
      termStarted = true;
    }
    setTimeout(() => { if (term) term.focus(); }, 100);
  }
}
(window as any).toggleTerminal = toggleTerminal;

function initTerminal(): void {
  const container = $('terminal-container');
  if (!container || !window.Terminal) return;
  term = new window.Terminal({
    cursorBlink: true,
    fontSize: 13,
    fontFamily: "'JetBrains Mono', monospace",
    theme: { background: '#08080A', foreground: '#ECECF0', cursor: '#E8A04F' },
  });
  if (window.FitAddon) {
    const fit = new window.FitAddon.FitAddon();
    term.loadAddon(fit);
    term.open(container);
    fit.fit();
  } else {
    term.open(container);
  }
  term.writeln('\x1b[1;33mButler Terminal\x1b[0m — type commands, output streamed from backend PTY.');
  term.onData((data: string) => {
    if (hasApi()) api().terminal_input(data);
  });
}

// ─── Voice ─────────────────────────────────────────────────
function toggleVoice(): void {
  if (hasApi()) api().toggle_voice();
  else showToast('语音：演示模式', 'info');
}
(window as any).toggleVoice = toggleVoice;

function toggleNotificationPanel(): void {
  // simple: cycle through a demo notification
  pushNotification('Butler', '暂无新通知', 'info');
}
(window as any).toggleNotificationPanel = toggleNotificationPanel;

// ═══════════════════════════════════════════════════════════
// BRIDGE CONTRACT — window.* callbacks invoked by backend
// via window.evaluate_js(...). MUST remain available.
// ═══════════════════════════════════════════════════════════

// AI streaming
(window as any).onAIStreamStart = (): void => {
  // ensure a fresh AI bubble exists for streaming
  if (!currentStreamId) {
    const msgs = $('messages');
    if (!msgs) return;
    currentStreamId = 'r' + Date.now();
    const aiMsg = el('div', 'msg ai');
    aiMsg.id = currentStreamId;
    aiMsg.innerHTML = `<div class="avatar">B</div><div class="bubble"></div>`;
    msgs.appendChild(aiMsg);
  }
  const b = document.querySelector(`#${currentStreamId} .bubble`);
  if (b) b.innerHTML = '';
};

(window as any).onAIStreamChunk = (chunk: any): void => {
  const b = document.querySelector(`#${currentStreamId} .bubble`);
  if (!b) return;
  if (typeof chunk === 'string') {
    b.innerHTML += escapeHtml(chunk).replace(/\n/g, '<br>');
  } else {
    // structured: code_block / data_table / chart / translation
    try {
      const obj = typeof chunk === 'string' ? JSON.parse(chunk) : chunk;
      if (obj.type === 'code_block') {
        b.innerHTML += `<pre>${escapeHtml(obj.content || '')}</pre>`;
      } else if (obj.content) {
        b.innerHTML += renderMarkdown(obj.content);
      } else {
        b.innerHTML += `<pre>${escapeHtml(JSON.stringify(obj, null, 2))}</pre>`;
      }
    } catch (_) {
      b.innerHTML += escapeHtml(String(chunk));
    }
  }
  const msgs = $('messages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
};

(window as any).onAIStreamEnd = (): void => {
  currentStreamId = null;
};

// Progress
(window as any).onProgressUpdate = (value: number): void => {
  const ts = $('taskStatus');
  if (ts) { ts.textContent = `运行中 ${value}%`; ts.style.color = 'var(--amber)'; }
};
(window as any).onProgressSync = (data: any): void => {
  // data: {task, progress, ...}
  if (data && typeof data.progress === 'number') {
    (window as any).onProgressUpdate(data.progress);
  }
};

// Focus mode
(window as any).onFocusStart = (_message: any): void => {
  document.body.style.background = 'radial-gradient(ellipse at center, rgba(232,160,79,0.1), var(--bg-0))';
  showToast('专注模式已开启', 'info');
};
(window as any).onFocusStop = (): void => {
  document.body.style.background = '';
};

// Editor
(window as any).openEditor = (content: string, filename: string): void => {
  switchView('chat');
  const msgs = $('messages');
  if (!msgs) return;
  const m = el('div', 'msg ai');
  m.innerHTML = `<div class="avatar">B</div><div class="bubble"><div style="font-family:var(--mono);font-size:11px;color:var(--text-mute);margin-bottom:6px">${escapeHtml(filename || 'untitled')}</div><pre>${escapeHtml(content || '')}</pre></div>`;
  msgs.appendChild(m);
  msgs.scrollTop = msgs.scrollHeight;
};

// Terminal output
(window as any).onTerminalOutput = (output: any): void => {
  if (term && output != null) term.write(String(output));
};

// Notifications
(window as any).onNotificationPush = (event: any): void => {
  const e = event || {};
  pushNotification(e.title || 'Butler', e.message || e.body || '', e.type || 'info');
};
(window as any).onNotificationClose = (_data: any): void => {
  const c = $('notification-container');
  if (c && c.firstChild) c.firstChild.remove();
};

// Window / breath-light states
(window as any).onWindowStates = (states: any): void => {
  // states: array of {id, title, active, ...}
  const box = $('activeSkills');
  if (!box) return;
  const arr = Array.isArray(states) ? states : [];
  if (!arr.length) { box.innerHTML = '<div style="font-size:11px;color:var(--text-mute)">暂无</div>'; return; }
  box.innerHTML = arr.slice(0, 8).map((s: any) =>
    `<div class="insp-skill"><span class="dot ${s.active ? 'on' : ''}"></span><span class="name">${escapeHtml(s.title || s.id || '')}</span></div>`
  ).join('');
};
(window as any).applyBreathLightMode = (_mode: string): void => {
  // inline / hud / off — visual hint only
  showToast('呼吸灯模式已更新', 'info');
};

// Voice status
(window as any).onVoiceStatusChange = (isListening: boolean): void => {
  const btn = $('btnVoice');
  if (btn) btn.style.color = isListening ? 'var(--coral)' : '';
  if (isListening) showToast('正在聆听…', 'info');
};

// Nostalgia / theme
(window as any).onNostalgiaMode = (): void => {
  document.body.classList.toggle('nostalgia');
  showToast('怀旧模式已切换', 'info');
};
(window as any).setTheme = (_theme: string): void => {
  // theme switching stub — industrial dark is the default theme
};

// Screen capture stub (backend may call ScreenCapture.openPanel)
(window as any).ScreenCapture = {
  openPanel: (): void => {
    pushNotification('截屏', '截屏面板功能开发中', 'info');
  },
};

// ─── Telemetry poll (real-time metrics) ───────────────────
async function pollMetrics(): Promise<void> {
  if (!hasApi()) {
    // demo values
    updateMetrics({ cpu: 12, memory_mb: 684, vector_count: 1284 });
    return;
  }
  try {
    const m = await api().get_realtime_metrics();
    updateMetrics(m || {});
  } catch (_) { /* ignore */ }
}

function updateMetrics(m: any): void {
  const cpu = m.cpu ?? m.cpu_percent ?? 0;
  const mem = m.memory_mb ?? m.memory ?? 0;
  const vec = m.vector_count ?? m.vectors ?? 0;
  const cpuEl = $('mCpu'), memEl = $('mMem'), vecEl = $('mVec');
  if (cpuEl) cpuEl.textContent = `${cpu}%`;
  if (memEl) memEl.textContent = `${mem} MB`;
  if (vecEl) vecEl.textContent = `${vec}`;
  const cpuBar = $('mCpuBar') as HTMLElement, memBar = $('mMemBar') as HTMLElement, vecBar = $('mVecBar') as HTMLElement;
  if (cpuBar) cpuBar.style.width = `${Math.min(100, cpu)}%`;
  if (memBar) memBar.style.width = `${Math.min(100, (mem / 2048) * 100)}%`;
  if (vecBar) vecBar.style.width = `${Math.min(100, (vec / 2000) * 100)}%`;
}

// ─── Init ──────────────────────────────────────────────────
window.addEventListener('pywebviewready', () => {
  const led = $('connLed'), txt = $('connText');
  if (led) { led.style.background = 'var(--green)'; }
  if (txt) txt.textContent = '已连接';
  loadModelConfig();
  loadSkills();
  pollMetrics();
  setInterval(pollMetrics, 5000);
});

// Fallback init (no pywebview, e.g. browser preview)
if (!hasApi()) {
  const led = $('connLed'), txt = $('connText');
  if (led) led.style.background = 'var(--text-mute)';
  if (txt) txt.textContent = '演示模式';
  pollMetrics();
  setInterval(pollMetrics, 5000);
}
