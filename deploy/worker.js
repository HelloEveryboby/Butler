// deploy/worker.js - Butler 一键部署单入口路由 Worker
// 托管于 Cloudflare Workers，支持通过 curl/irm 自动化按平台分发部署脚本

export default {
  async fetch(request) {
    const ua = request.headers.get('User-Agent') || '';
    const baseUrl = 'https://raw.githubusercontent.com/HelloEveryboby/Butler/main/scripts';

    // 依据 User-Agent 智能识别操作系统
    let targetScript = `${baseUrl}/install.sh`;
    if (ua.includes('PowerShell') || ua.includes('Windows') || ua.includes('PSParentPath')) {
      targetScript = `${baseUrl}/install.ps1`;
    }

    try {
      const res = await fetch(targetScript);
      if (!res.ok) {
        return new Response(`[Error] Failed to fetch target bootstrap script from repository: ${res.statusText}`, {
          status: 500,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' }
        });
      }

      const scriptContent = await res.text();
      return new Response(scriptContent, {
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-cache, no-store, must-revalidate'
        }
      });
    } catch (err) {
      return new Response(`[Error] Dispatcher execution failed: ${err.message}`, {
        status: 500,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' }
      });
    }
  }
};
