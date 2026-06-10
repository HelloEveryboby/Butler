let isTracking = false;

// Butler Bridge Helper
async function callButlerSkill(action, params = {}) {
    console.log("Calling Butler Skill:", action, params);
    try {
        if (window.pywebview && window.pywebview.api) {
            return await window.pywebview.api.call_skill('sys_cleaner_pro', action, params);
        }
    } catch (e) {
        console.error("Local Bridge call failed:", e);
    }

    // Try posting message to parent
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
            skill_id: 'sys_cleaner_pro',
            action: action,
            params: params,
            requestId: requestId
        }, '*');

        // Timeout
        setTimeout(() => {
            window.removeEventListener('message', handler);
            resolve({ status: "error", message: "Timeout waiting for Butler response" });
        }, 5000);
    });
}

async function toggleMonitor() {
    console.log("Toggle Monitor clicked, current isTracking:", isTracking);
    const btn = document.getElementById('btn-monitor');
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');
    const logBody = document.getElementById('log-output');

    if (!isTracking) {
        text.innerText = "准备快照中...";
        const data = await callButlerSkill('start_track');
        console.log("start_track response:", data);
        if (data && data.status === "tracking_started") {
            isTracking = true;
            btn.innerText = "🛑 捕获系统变更并分析";
            indicator.className = "status-tracking";
            text.innerText = "正在监视新软件安装...";
            logBody.innerHTML = "已生成初始快照。<br>请现在开始安装软件...";
        } else {
            text.innerText = "快照失败";
            logBody.innerHTML = `<span style="color:#f87171">错误: ${data ? data.message : 'Unknown'}</span>`;
        }
    } else {
        text.innerText = "分析差异中...";
        const data = await callButlerSkill('stop_track');
        console.log("stop_track response:", data);
        isTracking = false;
        btn.innerText = "⚡ 开启安装监视";
        indicator.className = "status-idle";

        if (data && data.status === "error") {
            text.innerText = "分析失败";
            logBody.innerHTML = `<span style="color:#f87171">错误: ${data.message}</span>`;
        } else if (data) {
            text.innerText = "分析完成";
            logBody.innerHTML = `
                <div style="color: #60a5fa; margin-bottom: 8px;">探测到系统变更:</div>
                • 新增注册表项: ${data.reg_added}<br>
                • 新增文件系统项: ${data.file_added}<br>
            `;

            // 自动化流程：如果开启了“静默模式”或用户希望一键完成
            if (data.file_added > 0 || data.reg_added > 0) {
                logBody.innerHTML += `<div style="margin-top: 8px; color: #fbbf24;">🚀 正在为您自动执行强力清理...</div>`;
                setTimeout(requestClean, 1000); // 延迟一秒执行，给用户一点视觉反馈
            } else {
                logBody.innerHTML += `<div style="margin-top: 8px; color: #71717a;">未检测到显著变更。</div>`;
            }
        }
    }
}

async function setupSilentMode() {
    const logBody = document.getElementById('log-output');
    logBody.innerHTML = "正在请求一次性授权以开启静默清理通道...";
    const data = await callButlerSkill('setup_elevation');
    alert(data.message);
    logBody.innerHTML = data.message;
}

async function requestClean() {
    const logBody = document.getElementById('log-output');
    logBody.innerHTML += "<br><span style=\"color: #fbbf24;\">正在请求系统级提权授权...</span>";

    const data = await callButlerSkill('execute_clean');
    if (data && data.message) {
        alert(data.message);
        if (data.message.includes("成功")) {
            document.getElementById('btn-clean').disabled = true;
            logBody.innerHTML += "<br><span style=\"color: #10b981;\">清理执行完毕。</span>";
        }
    }
}
