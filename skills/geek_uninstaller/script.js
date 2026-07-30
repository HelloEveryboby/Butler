// Geek Uninstaller — Butler 前端桥接逻辑
// 复用 sys_cleaner 的 pywebview / postMessage 双通道调用约定

const SKILL_ID = 'geek_uninstaller';

// Butler Bridge Helper
async function callButlerSkill(action, params = {}) {
    console.log("Calling Butler Skill:", action, params);
    try {
        if (window.pywebview && window.pywebview.api) {
            return await window.pywebview.api.call_skill(SKILL_ID, action, params);
        }
    } catch (e) {
        console.error("Local Bridge call failed:", e);
    }

    // 回退:向父窗口 postMessage(iframe 嵌入场景)
    return new Promise((resolve) => {
        const requestId = Math.random().toString(36).substring(7);
        const handler = (event) => {
            if (event.data && event.data.requestId === requestId) {
                window.removeEventListener('message', handler);
                resolve(event.data.result);
            }
        };
        window.addEventListener('message', handler);
        window.parent.postMessage({
            type: 'skill_call',
            skill_id: SKILL_ID,
            action: action,
            params: params,
            requestId: requestId
        }, '*');
        setTimeout(() => {
            window.removeEventListener('message', handler);
            resolve({ status: "error", message: "Butler 响应超时" });
        }, 30000);
    });
}

// ---------------- 通用辅助 ----------------
function setStatus(text, cls) {
    document.getElementById('status-text').innerText = text;
    document.getElementById('status-indicator').className = cls || 'status-idle';
}

function log(html) {
    const body = document.getElementById('log-output');
    const ts = new Date().toLocaleTimeString();
    body.innerHTML = `<span class="log-ts">[${ts}]</span> ${html}<br>` + body.innerHTML;
}

function bar(percent, width = 14) {
    const filled = Math.round(percent / 100 * width);
    return '█'.repeat(filled) + '░'.repeat(width - filled) + ` ${percent.toFixed(1)}%`;
}

function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

// ---------------- Tab 切换 ----------------
function switchTab(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
}

// ---------------- 软件 Tab ----------------
async function loadSoftware() {
    setStatus('扫描已安装软件...', 'status-tracking');
    log('🔍 开始扫描已安装软件');
    const data = await callButlerSkill('list_software');
    const box = document.getElementById('software-list');
    if (data.status !== 'ok') {
        setStatus('扫描失败', 'status-idle');
        log(`<span style="color:#f87171">扫描失败: ${data.message}</span>`);
        return;
    }
    setStatus(`扫描完成 · ${data.count} 个软件`, 'status-idle');
    log(`<span style="color:#10b981">扫描完成,共 ${data.count} 个软件</span>`);
    if (!data.count) {
        box.innerHTML = '<div class="empty-hint">未检测到已安装软件</div>';
        return;
    }
    box.innerHTML = data.items.map((it, i) => `
        <div class="data-row" onclick="document.getElementById('uninstall-name').value='${escapeHtml(it.name)}'">
            <div class="row-main">
                <span class="row-name">${escapeHtml(it.name)}</span>
                <span class="row-meta">${escapeHtml(it.version || '-')} · ${escapeHtml(it.source)}</span>
            </div>
            <span class="row-size">${escapeHtml(it.size_text)}</span>
        </div>
    `).join('');
}

async function doUninstall() {
    const name = document.getElementById('uninstall-name').value.trim();
    if (!name) { alert('请输入软件名'); return; }
    const dryRun = document.getElementById('dry-run-uninstall').checked;
    setStatus('深度卸载中...', 'status-tracking');
    log(`🛡️ 卸载 ${name} (dry_run=${dryRun})`);
    const data = await callButlerSkill('uninstall', { name, dry_run: dryRun });
    if (data.status === 'not_found') {
        setStatus('未找到软件', 'status-idle');
        log(`<span style="color:#fbbf24">${data.message}</span>`);
        alert(data.message);
        return;
    }
    if (data.status !== 'ok') {
        setStatus('卸载失败', 'status-idle');
        log(`<span style="color:#f87171">卸载失败: ${data.message}</span>`);
        return;
    }
    const mode = data.dry_run ? '模拟' : '实际';
    setStatus(`${mode}卸载完成`, 'status-idle');
    let detail = `<b>${mode}卸载完成:${escapeHtml(data.name)}</b><br>` +
        `• 卸载程序:${data.uninstalled ? '已执行' : '跳过'}<br>` +
        `• 残留扫描:${data.leftover_count} 项 (约 ${formatBytes(data.leftover_total_size)})<br>`;
    if (!data.dry_run) {
        detail += `• 已清理:${data.cleaned} 项,释放 ${data.freed_text}<br>`;
    } else {
        detail += `<span style="color:#fbbf24">• 这是模拟,去掉勾选"模拟运行"以实际执行</span><br>`;
    }
    if (data.leftovers && data.leftovers.length) {
        detail += '<div class="leftover-list">' + data.leftovers.map(l =>
            `<div class="leftover-item"><span class="lk">${escapeHtml(l.kind)}</span> ${escapeHtml(l.path)} <span class="ls">${escapeHtml(l.size_text)}</span></div>`
        ).join('') + '</div>';
    }
    log(detail);
}

// ---------------- 清理 Tab ----------------
async function scanJunk() {
    setStatus('扫描垃圾文件...', 'status-tracking');
    log('♻️ 开始扫描系统垃圾');
    const data = await callButlerSkill('scan_junk');
    const box = document.getElementById('junk-list');
    if (data.status !== 'ok') {
        setStatus('扫描失败', 'status-idle');
        log(`<span style="color:#f87171">扫描失败: ${data.message}</span>`);
        return;
    }
    setStatus(`扫描完成 · 可释放 ${data.total_size_text}`, 'status-idle');
    log(`<span style="color:#10b981">发现 ${data.count} 处垃圾,可释放 ${data.total_size_text}</span>`);
    document.getElementById('btn-clean-junk').disabled = !data.count;
    if (!data.count) {
        box.innerHTML = '<div class="empty-hint">系统很干净,未发现垃圾</div>';
        return;
    }
    box.innerHTML = data.items.map((it, i) => `
        <div class="data-row">
            <input type="checkbox" class="row-check" data-idx="${i}" checked>
            <div class="row-main">
                <span class="row-name">${escapeHtml(it.description)}</span>
                <span class="row-meta">${escapeHtml(it.category)} · ${escapeHtml(it.path)}</span>
            </div>
            <span class="row-size">${escapeHtml(it.size_text)}</span>
        </div>
    `).join('');
    window._junkItems = data.items;
}

async function cleanJunk() {
    const dryRun = document.getElementById('dry-run-clean').checked;
    setStatus('清理中...', 'status-tracking');
    log(`🚀 清理垃圾 (dry_run=${dryRun})`);
    const data = await callButlerSkill('clean_junk', { dry_run: dryRun });
    if (data.status !== 'ok') {
        setStatus('清理失败', 'status-idle');
        log(`<span style="color:#f87171">清理失败: ${data.message}</span>`);
        return;
    }
    const mode = data.dry_run ? '模拟' : '实际';
    setStatus(`${mode}清理完成`, 'status-idle');
    log(`<b>${mode}清理完成</b>:清理 ${data.cleaned} 项,跳过 ${data.skipped},${data.dry_run ? '预计释放' : '已释放'} <b>${data.freed_text}</b>${data.dry_run ? '(去掉勾选模拟运行以实际执行)' : ''}`);
}

// ---------------- 监控 Tab ----------------
function formatBytes(n) {
    if (!n) return '0 B';
    const u = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return n.toFixed(1) + ' ' + u[i];
}

async function loadSnapshot() {
    setStatus('采集系统快照...', 'status-tracking');
    const data = await callButlerSkill('system_info');
    const box = document.getElementById('monitor-body');
    if (data.status !== 'ok') {
        setStatus('采集失败', 'status-idle');
        log(`<span style="color:#f87171">采集失败: ${data.message}</span>`);
        return;
    }
    setStatus('快照已采集', 'status-idle');
    log('📸 系统快照已采集');
    const s = data.system, c = data.cpu, m = data.memory, n = data.network;
    const cores = c.per_core.map(x => x.toFixed(0) + '%').join('  ');
    let disksHtml = '';
    if (data.disks && data.disks.length) {
        disksHtml = data.disks.map(d =>
            `<div class="metric-row"><span class="mk">磁盘 ${escapeHtml(d.mountpoint)}</span><span class="mv">${bar(d.percent)}</span><span class="ms">${d.used_text} / ${d.total_text}</span></div>`
        ).join('');
    } else {
        disksHtml = '<div class="metric-row"><span class="mk">磁盘</span><span class="mv dim">当前环境无可读分区</span></div>';
    }
    box.innerHTML = `
        <div class="snapshot">
            <div class="sys-info">${escapeHtml(s.system)} ${escapeHtml(s.release)} · ${escapeHtml(s.machine)} · ${s.cpu_count_physical}核/${s.cpu_count}线程 · 运行 ${escapeHtml(data.uptime_text)}</div>
            <div class="metric-row"><span class="mk">CPU</span><span class="mv">${bar(c.percent)}</span><span class="ms">${c.count}核 ${c.freq_mhz}MHz</span></div>
            <div class="metric-row"><span class="mk">每核</span><span class="mv mono">${cores}</span></div>
            <div class="metric-row"><span class="mk">内存</span><span class="mv">${bar(m.percent)}</span><span class="ms">${m.used_text} / ${m.total_text}</span></div>
            ${m.swap_total ? `<div class="metric-row"><span class="mk">Swap</span><span class="mv">${bar(m.swap_percent)}</span><span class="ms">${formatBytes(m.swap_used)} / ${formatBytes(m.swap_total)}</span></div>` : ''}
            ${disksHtml}
            <div class="metric-row"><span class="mk">网络</span><span class="mv mono">↑ ${formatBytes(n.bytes_sent)} ↓ ${formatBytes(n.bytes_recv)}</span></div>
        </div>
    `;
}

async function loadTop() {
    setStatus('采集进程...', 'status-tracking');
    const data = await callButlerSkill('top_processes', { limit: 12, sort_by: 'cpu' });
    const box = document.getElementById('monitor-body');
    if (data.status !== 'ok') {
        setStatus('采集失败', 'status-idle');
        log(`<span style="color:#f87171">采集失败: ${data.message}</span>`);
        return;
    }
    setStatus(`进程排行 · ${data.count} 条`, 'status-idle');
    log('🏆 进程排行已采集');
    box.innerHTML = `
        <div class="proc-table">
            <div class="proc-head">
                <span class="pc-pid">PID</span><span class="pc-name">名称</span>
                <span class="pc-cpu">CPU%</span><span class="pc-mem">内存</span>
            </div>
            ${data.items.map(p => `
                <div class="proc-row" title="${escapeHtml(p.command)}">
                    <span class="pc-pid">${p.pid}</span>
                    <span class="pc-name">${escapeHtml(p.name)}</span>
                    <span class="pc-cpu">${p.cpu_percent.toFixed(1)}</span>
                    <span class="pc-mem">${escapeHtml(p.memory_text)}</span>
                </div>
            `).join('')}
        </div>
    `;
}
