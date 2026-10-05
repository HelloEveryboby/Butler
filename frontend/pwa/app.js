/* ============================================================
   Butler 翻译 PWA 前端逻辑（纯原生 JS，无框架、无 CDN）
   - 粘贴文本 → 双语对照（段落交错）
   - 拍照 / 选图 → OCR → 双语对照
   - 上传文件 → 双语导出
   - 翻译源 / 目标语言 / 术语表 / 历史（localStorage）
   - 后端不可达时给出明确中文提示，不白屏
   ============================================================ */
"use strict";

/* ---------------- 全局状态 ---------------- */
const state = {
  apiBase: localStorage.getItem("butlerPwa.apiBase") || "",   // 空 = 同源
  toLang: localStorage.getItem("butlerPwa.toLang") || "zh-CN",
  providers: [],
  languages: [],
  online: null,          // 后端可达性：null 未知 / true / false
  editingTerm: null,     // 术语表编辑中的原词
  lastBilingual: [],     // 最近一次双语结果 [{source,target}]
};

/* 备用语言列表：/api/languages 不可达时 UI 仍可用 */
const FALLBACK_LANGUAGES = [
  { code: "zh-CN", name: "中文（简体）" },
  { code: "zh-TW", name: "中文（繁体）" },
  { code: "en", name: "英语" },
  { code: "ja", name: "日语" },
  { code: "ko", name: "韩语" },
  { code: "fr", name: "法语" },
  { code: "de", name: "德语" },
  { code: "es", name: "西班牙语" },
  { code: "pt", name: "葡萄牙语" },
  { code: "ru", name: "俄语" },
  { code: "ar", name: "阿拉伯语" },
  { code: "it", name: "意大利语" },
  { code: "th", name: "泰语" },
  { code: "vi", name: "越南语" },
  { code: "id", name: "印尼语" },
  { code: "nl", name: "荷兰语" },
  { code: "pl", name: "波兰语" },
  { code: "tr", name: "土耳其语" },
];

/* ---------------- 小工具 ---------------- */
const $ = (id) => document.getElementById(id);

function toast(msg, ms = 2200) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), ms);
}

function setOnline(ok) {
  state.online = ok;
  const badge = $("netBadge");
  badge.classList.remove("badge-ok", "badge-bad", "badge-unknown");
  if (ok === true) {
    badge.textContent = "后端在线";
    badge.classList.add("badge-ok");
    $("offlineBanner").classList.add("hidden");
  } else if (ok === false) {
    badge.textContent = "后端离线";
    badge.classList.add("badge-bad");
    $("offlineBanner").classList.remove("hidden");
  } else {
    badge.textContent = "检测中…";
    badge.classList.add("badge-unknown");
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function splitParagraphs(text) {
  let parts = String(text).split(/\n\s*\n/).map((s) => s.trim()).filter(Boolean);
  if (parts.length === 1 && parts[0].includes("\n")) {
    parts = parts[0].split("\n").map((s) => s.trim()).filter(Boolean);
  }
  return parts;
}

function langName(code) {
  const hit = (state.languages.length ? state.languages : FALLBACK_LANGUAGES)
    .find((l) => l.code === code);
  return hit ? hit.name : code;
}

/* ---------------- API 封装（含离线兜底） ---------------- */
async function api(path, options = {}) {
  const url = state.apiBase + path;
  let res;
  try {
    res = await fetch(url, Object.assign({
      headers: { "Content-Type": "application/json" },
    }, options));
  } catch (e) {
    setOnline(false);
    throw new Error(
      "无法连接后端服务（" + (state.apiBase || "当前站点同源") + "）。\n" +
      "请确认已运行：python3 frontend/pwa/server.py --port 8766\n" +
      "并用 http://<电脑IP>:8766/ 打开本页；或在右上角 ⚙ 设置里填写正确的后端地址。"
    );
  }
  setOnline(true);
  let data = {};
  try {
    data = await res.json();
  } catch (e) {
    /* 非 JSON 响应，走下面的状态判断 */
  }
  if (!res.ok) {
    throw new Error(data.error || ("请求失败（HTTP " + res.status + "）"));
  }
  return data;
}

/* ---------------- 双语结果渲染 ---------------- */
function renderBilingual(container, segments) {
  container.innerHTML = "";
  if (!segments || !segments.length) {
    container.innerHTML = '<p class="placeholder">没有可显示的翻译结果。</p>';
    return;
  }
  for (const seg of segments) {
    const block = document.createElement("div");
    block.className = "bi-block";
    const src = document.createElement("p");
    src.className = "bi-src";
    src.textContent = seg.source;
    const tgt = document.createElement("p");
    tgt.className = "bi-tgt";
    tgt.textContent = seg.target;
    block.appendChild(src);
    block.appendChild(tgt);
    container.appendChild(block);
  }
}

function renderError(container, err) {
  const box = document.createElement("div");
  box.className = "error-box";
  box.textContent = err && err.message ? err.message : String(err);
  container.innerHTML = "";
  container.appendChild(box);
}

/* ---------------- 历史（localStorage） ---------------- */
function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem("butlerPwa.history") || "[]");
  } catch (e) {
    return [];
  }
}

function saveHistory(list) {
  localStorage.setItem("butlerPwa.history", JSON.stringify(list.slice(0, 100)));
}

function addHistory(source, target) {
  const list = loadHistory();
  list.unshift({ ts: Date.now(), source, target, to: state.toLang });
  saveHistory(list);
  renderHistory();
}

function renderHistory() {
  const list = loadHistory();
  const box = $("historyList");
  if (!list.length) {
    box.innerHTML = '<p class="placeholder">暂无历史记录。</p>';
    return;
  }
  box.innerHTML = "";
  list.forEach((item, idx) => {
    const el = document.createElement("div");
    el.className = "hist-item";
    const when = new Date(item.ts).toLocaleString("zh-CN", { hour12: false });
    el.innerHTML =
      '<div class="hist-meta"><span>' + escapeHtml(langName(item.to)) + "</span><span>" +
      escapeHtml(when) + "</span></div>" +
      '<p class="hist-src">' + escapeHtml(item.source) + "</p>" +
      '<p class="hist-tgt">' + escapeHtml(item.target) + "</p>";
    const row = document.createElement("div");
    row.className = "row";
    const btnReuse = document.createElement("button");
    btnReuse.className = "btn small";
    btnReuse.textContent = "复用原文";
    btnReuse.addEventListener("click", () => {
      switchTab("translate");
      $("srcText").value = item.source;
      toast("已填入原文，点「翻译」重新翻译");
    });
    const btnDel = document.createElement("button");
    btnDel.className = "btn small danger";
    btnDel.textContent = "删除";
    btnDel.addEventListener("click", () => {
      const cur = loadHistory();
      cur.splice(idx, 1);
      saveHistory(cur);
      renderHistory();
    });
    row.appendChild(btnReuse);
    row.appendChild(btnDel);
    el.appendChild(row);
    box.appendChild(el);
  });
}

/* ---------------- Tab 切换 ---------------- */
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach((el) => el.classList.remove("active"));
  const tab = $("tab-" + name);
  if (tab) tab.classList.add("active");
  const btn = document.querySelector('.tab-btn[data-tab="' + name + '"]');
  if (btn) btn.classList.add("active");
  window.scrollTo({ top: 0 });
}

/* ---------------- 健康检查 ---------------- */
async function checkHealth() {
  try {
    const data = await api("/api/health");
    setOnline(true);
    // 顺带刷新语言列表（失败不影响主流程，UI 用备用列表）
    try {
      const langData = await api("/api/languages");
      if (langData.languages && langData.languages.length) {
        state.languages = langData.languages;
        renderLangOptions();
      }
    } catch (e) {
      /* 语言列表获取失败：继续用备用列表 */
    }
    if (data.translate_system !== "ok") {
      $("offlineDetail").textContent =
        "后端已连接，但翻译后端不可用：" + data.translate_system;
      $("offlineBanner").classList.remove("hidden");
    }
    if (data.providers && data.providers.length) {
      state.providers = data.providers;
      renderProviderOptions(data.active_provider);
    }
  } catch (e) {
    setOnline(false);
    $("offlineDetail").textContent = e.message;
    $("offlineBanner").classList.remove("hidden");
  }
}

/* ---------------- 翻译 ---------------- */
async function doTranslate(text, resultEl, save) {
  const paras = splitParagraphs(text);
  if (!paras.length) {
    toast("请先输入要翻译的文本");
    return;
  }
  const btns = document.querySelectorAll(".btn.primary");
  btns.forEach((b) => { b.disabled = true; });
  try {
    const data = await api("/api/translate", {
      method: "POST",
      body: JSON.stringify({ texts: paras, to: state.toLang, from: "auto" }),
    });
    state.lastBilingual = data.segments || [];
    renderBilingual(resultEl, data.segments);
    if (save) addHistory(text, data.translated);
    toast("翻译完成（" + (data.count || state.lastBilingual.length) + " 段）");
  } catch (e) {
    renderError(resultEl, e);
    toast("翻译失败，详见结果区");
  } finally {
    btns.forEach((b) => { b.disabled = false; });
  }
}

async function copyText(text, label) {
  if (!text) {
    toast("没有可复制的内容");
    return;
  }
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    toast(label + "已复制");
  } catch (e) {
    toast("复制失败：" + e.message);
  }
}

/* ---------------- OCR ---------------- */
let ocrImageBase64 = "";

function handleOcrFile(file) {
  if (!file) return;
  if (!/^image\//.test(file.type)) {
    toast("请选择图片文件");
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    ocrImageBase64 = String(reader.result);
    const img = $("ocrPreview");
    img.src = ocrImageBase64;
    img.classList.remove("hidden");
  };
  reader.readAsDataURL(file);
}

async function doOcr() {
  if (!ocrImageBase64) {
    toast("请先拍照或选择图片");
    return;
  }
  const btn = $("btnOcr");
  btn.disabled = true;
  btn.textContent = "识别中…";
  try {
    const data = await api("/api/ocr", {
      method: "POST",
      body: JSON.stringify({ image_base64: ocrImageBase64 }),
    });
    const text = (data.text || "").trim();
    $("ocrText").value = text;
    if (text) {
      toast("识别成功，置信度 " + Math.round((data.confidence || 0) * 100) + "%");
    } else {
      toast("未识别到文字，请换一张更清晰的图片");
    }
  } catch (e) {
    renderError($("ocrResult"), e);
    toast("OCR 失败，详见结果区");
  } finally {
    btn.disabled = false;
    btn.textContent = "识别文字";
  }
}

/* ---------------- 文件双语导出 ---------------- */
let expFileObj = null;

function b64ToBlob(b64, mime) {
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return new Blob([arr], { type: mime || "application/octet-stream" });
}

async function doExport() {
  const status = $("expStatus");
  const dl = $("expDownload");
  dl.classList.add("hidden");
  if (!expFileObj) {
    status.textContent = "请先选择文件。";
    return;
  }
  if (expFileObj.size > 20 * 1024 * 1024) {
    status.textContent = "文件超过 20MB，移动端导出请用更小的文件。";
    return;
  }
  const format = $("expFormat").value;
  status.textContent = "正在读取并翻译，请稍候…（大文件耗时较长）";
  const btn = $("btnExport");
  btn.disabled = true;
  try {
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new Error("文件读取失败"));
      reader.readAsDataURL(expFileObj);
    });
    const b64 = dataUrl.split(",", 2)[1] || "";
    const res = await api("/api/export", {
      method: "POST",
      body: JSON.stringify({
        file_base64: b64,
        filename: expFileObj.name,
        to: state.toLang,
        format: format,
      }),
    });
    const blob = b64ToBlob(res.file_base64, res.mime);
    const url = URL.createObjectURL(blob);
    dl.href = url;
    dl.download = res.filename || "bilingual.txt";
    dl.classList.remove("hidden");
    status.textContent =
      "生成成功：" + (res.filename || "") + "（" + Math.round((res.size || blob.size) / 1024) +
      " KB，引擎：" + (res.engine === "doc_export" ? "doc_export" : "内置兜底") + "），点下方按钮下载。";
    toast("双语文件已生成");
  } catch (e) {
    status.textContent = "导出失败：" + (e && e.message ? e.message : String(e));
    toast("导出失败，详见提示");
  } finally {
    btn.disabled = false;
  }
}

/* ---------------- 术语表 ---------------- */
async function renderTerms() {
  const box = $("termList");
  try {
    const data = await api("/api/glossary");
    const terms = data.terms || {};
    const keys = Object.keys(terms);
    $("termCount").textContent = String(keys.length);
    if (!keys.length) {
      box.innerHTML = '<p class="placeholder">还没有术语。在上面添加第一条吧。</p>';
      return;
    }
    box.innerHTML = "";
    for (const src of keys) {
      const item = document.createElement("div");
      item.className = "term-item";
      const pair = document.createElement("div");
      pair.className = "term-pair";
      pair.innerHTML = escapeHtml(src) + '<span class="arrow">→</span>' + escapeHtml(terms[src]);
      const btnEdit = document.createElement("button");
      btnEdit.className = "btn small";
      btnEdit.textContent = "编辑";
      btnEdit.addEventListener("click", () => startEditTerm(src, terms[src]));
      const btnDel = document.createElement("button");
      btnDel.className = "btn small danger";
      btnDel.textContent = "删除";
      btnDel.addEventListener("click", async () => {
        try {
          await api("/api/glossary?source=" + encodeURIComponent(src), { method: "DELETE" });
          toast("已删除：" + src);
          renderTerms();
        } catch (e) {
          toast("删除失败：" + e.message);
        }
      });
      item.appendChild(pair);
      item.appendChild(btnEdit);
      item.appendChild(btnDel);
      box.appendChild(item);
    }
  } catch (e) {
    renderError(box, e);
  }
}

function startEditTerm(src, tgt) {
  state.editingTerm = src;
  $("termSrc").value = src;
  $("termTgt").value = tgt;
  $("termEditTip").classList.remove("hidden");
  $("btnTermEditCancel").classList.remove("hidden");
  $("btnTermAdd").textContent = "保存修改";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function cancelEditTerm() {
  state.editingTerm = null;
  $("termSrc").value = "";
  $("termTgt").value = "";
  $("termEditTip").classList.add("hidden");
  $("btnTermEditCancel").classList.add("hidden");
  $("btnTermAdd").textContent = "添加术语";
}

async function saveTerm() {
  const src = $("termSrc").value.trim();
  const tgt = $("termTgt").value.trim();
  if (!src || !tgt) {
    toast("原文术语和固定译法都要填写");
    return;
  }
  try {
    if (state.editingTerm && state.editingTerm !== src) {
      // 原词被改动：删旧条目再新增
      await api("/api/glossary?source=" + encodeURIComponent(state.editingTerm),
        { method: "DELETE" });
    }
    await api("/api/glossary", {
      method: "POST",
      body: JSON.stringify({ source: src, target: tgt }),
    });
    toast(state.editingTerm ? "术语已更新" : "术语已添加");
    cancelEditTerm();
    renderTerms();
  } catch (e) {
    toast("保存失败：" + e.message);
  }
}

/* ---------------- 设置 ---------------- */
function renderLangOptions() {
  const sel = $("setToLang");
  const langs = state.languages.length ? state.languages : FALLBACK_LANGUAGES;
  sel.innerHTML = "";
  for (const l of langs) {
    const opt = document.createElement("option");
    opt.value = l.code;
    opt.textContent = l.name;
    if (l.code === state.toLang) opt.selected = true;
    sel.appendChild(opt);
  }
  $("toLangLabel").textContent = langName(state.toLang);
}

function renderProviderOptions(activeId) {
  const sel = $("setProvider");
  if (!sel) return;
  const current = activeId || sel.value;
  sel.innerHTML = "";
  if (!state.providers.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "（后端不可达，暂无翻译源）";
    sel.appendChild(opt);
    return;
  }
  for (const p of state.providers) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name + (p.api_key_set ? "" : "（未配 Key）");
    if (p.id === current) opt.selected = true;
    sel.appendChild(opt);
  }
  const hit = state.providers.find((p) => p.id === (current || state.providers[0].id));
  $("providerLabel").textContent = hit ? hit.name : "默认";
}

function openSettings() {
  renderLangOptions();
  renderProviderOptions();
  $("setApiBase").value = state.apiBase;
  $("settingsMask").classList.remove("hidden");
  $("settingsSheet").classList.remove("hidden");
}

function closeSettings() {
  $("settingsMask").classList.add("hidden");
  $("settingsSheet").classList.add("hidden");
}

/* ---------------- 图标（canvas 生成 apple-touch-icon） ---------------- */
function generateAppleTouchIcon() {
  try {
    const size = 180;
    const cv = document.createElement("canvas");
    cv.width = size;
    cv.height = size;
    const ctx = cv.getContext("2d");
    const grad = ctx.createLinearGradient(0, 0, size, size);
    grad.addColorStop(0, "#2563eb");
    grad.addColorStop(1, "#7c3aed");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 100px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("译", size / 2, size / 2 + 6);
    const link = document.createElement("link");
    link.rel = "apple-touch-icon";
    link.href = cv.toDataURL("image/png");
    document.head.appendChild(link);
  } catch (e) {
    /* canvas 不可用时忽略，不影响功能 */
  }
}

/* ---------------- Service Worker 注册 ---------------- */
function registerSW() {
  if (!("serviceWorker" in navigator)) return;
  if (location.protocol !== "http:" && location.protocol !== "https:") return;
  navigator.serviceWorker.register("sw.js").catch((e) => {
    console.warn("Service Worker 注册失败：", e);
  });
}

/* ---------------- 事件绑定 ---------------- */
function bindEvents() {
  // Tab 切换
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // 文本翻译
  $("btnTranslate").addEventListener("click", () => {
    doTranslate($("srcText").value, $("resultBox"), true);
  });
  $("btnClearText").addEventListener("click", () => {
    $("srcText").value = "";
    $("resultBox").innerHTML =
      '<p class="placeholder">翻译结果会显示在这里（原文在上、译文在下，段落交错）。</p>';
    state.lastBilingual = [];
  });
  $("btnCopyBilingual").addEventListener("click", () => {
    const text = state.lastBilingual
      .map((s) => s.source + "\n" + s.target).join("\n\n");
    copyText(text, "双语内容");
  });
  $("btnCopyTarget").addEventListener("click", () => {
    const text = state.lastBilingual.map((s) => s.target).join("\n\n");
    copyText(text, "译文");
  });

  // OCR
  $("ocrFile").addEventListener("change", (e) => handleOcrFile(e.target.files[0]));
  $("btnOcr").addEventListener("click", doOcr);
  $("btnOcrClear").addEventListener("click", () => {
    ocrImageBase64 = "";
    $("ocrFile").value = "";
    $("ocrPreview").classList.add("hidden");
    $("ocrText").value = "";
    $("ocrResult").innerHTML = '<p class="placeholder">识别文本的翻译结果会显示在这里。</p>';
  });
  $("btnOcrTranslate").addEventListener("click", () => {
    doTranslate($("ocrText").value, $("ocrResult"), true);
  });

  // 文件导出
  $("expFile").addEventListener("change", (e) => {
    expFileObj = e.target.files[0] || null;
    $("expFileName").textContent = expFileObj
      ? "已选：" + expFileObj.name + "（" + Math.round(expFileObj.size / 1024) + " KB）"
      : "未选择文件";
    $("expDownload").classList.add("hidden");
  });
  $("btnExport").addEventListener("click", doExport);

  // 术语表
  $("btnTermAdd").addEventListener("click", saveTerm);
  $("btnTermEditCancel").addEventListener("click", cancelEditTerm);
  $("btnTermReload").addEventListener("click", renderTerms);

  // 历史
  $("btnHistoryClear").addEventListener("click", () => {
    if (confirm("确定清空本机翻译历史吗？")) {
      saveHistory([]);
      renderHistory();
      toast("历史已清空");
    }
  });

  // 设置
  $("btnSettings").addEventListener("click", openSettings);
  $("btnQuickSettings").addEventListener("click", openSettings);
  $("btnSettingsClose").addEventListener("click", closeSettings);
  $("settingsMask").addEventListener("click", closeSettings);
  $("setToLang").addEventListener("change", (e) => {
    state.toLang = e.target.value;
    localStorage.setItem("butlerPwa.toLang", state.toLang);
    $("toLangLabel").textContent = langName(state.toLang);
    toast("目标语言：" + langName(state.toLang));
  });
  $("btnSetProvider").addEventListener("click", async () => {
    const id = $("setProvider").value;
    if (!id) return;
    try {
      const data = await api("/api/providers", {
        method: "POST",
        body: JSON.stringify({ id, select: true }),
      });
      state.providers = data.providers || [];
      renderProviderOptions(data.active);
      toast("默认翻译源已切换");
    } catch (e) {
      toast("切换失败：" + e.message);
    }
  });
  $("btnSaveKey").addEventListener("click", async () => {
    const id = $("setProvider").value;
    const key = $("setApiKey").value.trim();
    if (!id) return;
    if (!key) {
      toast("请先填写 API Key");
      return;
    }
    try {
      const data = await api("/api/providers", {
        method: "POST",
        body: JSON.stringify({ id, api_key: key }),
      });
      state.providers = data.providers || [];
      renderProviderOptions(data.active);
      $("setApiKey").value = "";
      toast("API Key 已保存（仅存后端进程内）");
    } catch (e) {
      toast("保存失败：" + e.message);
    }
  });
  $("btnSaveApiBase").addEventListener("click", () => {
    state.apiBase = $("setApiBase").value.trim().replace(/\/+$/, "");
    localStorage.setItem("butlerPwa.apiBase", state.apiBase);
    toast("后端地址已保存");
    checkHealth();
    renderTerms();
  });

  // 网络状态变化时重查
  window.addEventListener("online", checkHealth);
  window.addEventListener("offline", () => setOnline(false));
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) checkHealth();
  });
}

/* ---------------- 启动 ---------------- */
function init() {
  generateAppleTouchIcon();
  bindEvents();
  renderLangOptions();
  renderHistory();
  renderTerms();
  registerSW();
  checkHealth();
  // 每 60 秒轻量探测一次后端
  setInterval(checkHealth, 60000);
}

document.addEventListener("DOMContentLoaded", init);
