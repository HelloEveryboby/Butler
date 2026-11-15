/**
 * Win11 应用页面模板 —— 四个工作区全部由 TypeScript 生成。
 * 保留既有 DOM id / class，确保 DAG、时光机、技能抽屉等模块仍可挂载。
 */

import { icon, type IconName } from './icons';

export interface NavItem {
  id: string;
  label: string;
  icon: IconName;
  x: number;
  y: number;
  group: '工作区' | '系统';
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'chat', label: '智能助手', icon: 'chat', x: 0, y: 0, group: '工作区' },
  { id: 'timemachine', label: '时光监控', icon: 'clock', x: 1, y: 0, group: '工作区' },
  { id: 'dag', label: '任务画布', icon: 'flow', x: 0, y: 1, group: '工作区' },
  { id: 'skills', label: '技能仓储', icon: 'box', x: 1, y: 1, group: '工作区' },
];

interface QuickAction {
  icon: string;
  title: string;
  desc: string;
  action: string;
}

const COMMON_ACTIONS: QuickAction[] = [
  { icon: 'fa-shield-halved', title: '系统自检与审计', desc: '扫描安全配置、开放端口与环境沙箱', action: "triggerQuickAction('系统自检与安全审计')" },
  { icon: 'fa-broom', title: '一键清理垃圾', desc: '扫描并清除冗余缓存，恢复磁盘空间', action: "triggerQuickAction('一键清理系统垃圾')" },
  { icon: 'fa-wave-square', title: '本地 FFT 降噪', desc: 'C++ 音频算法降阶滤波与离线提取', action: "triggerQuickAction('运行本地 FFT 音频降噪')" },
  { icon: 'fa-network-wired', title: '局域网同步', desc: '一键同步代码与资产到局域网节点', action: "triggerQuickAction('开启局域网同步')" },
];

const APP_ACTIONS: QuickAction[] = [
  { icon: 'fa-code-branch', title: '会话模式', desc: '本地 / Worktree / 云端模式切换', action: 'FeaturesHub.openSessionModeModal()' },
  { icon: 'fa-code-compare', title: 'Git 工具', desc: 'Diff / Commit / Push / PR 管理', action: 'FeaturesHub.openGitPanel()' },
  { icon: 'fa-folder-tree', title: '多项目', desc: '跨项目多任务并行管理', action: 'FeaturesHub.openProjectManager()' },
  { icon: 'fa-globe', title: '应用内浏览器', desc: '预览 Web 应用并评论', action: 'FeaturesHub.launchBrowser()' },
  { icon: 'fa-window-restore', title: '浮动窗口', desc: '弹出独立对话线程', action: 'FeaturesHub.createPopup()' },
  { icon: 'fa-desktop', title: '计算机使用', desc: '操作桌面应用、测试 GUI', action: 'FeaturesHub.launchComputerUse()' },
  { icon: 'fa-microphone-lines', title: '语音听写', desc: '按住录音发送指令', action: 'FeaturesHub.launchVoiceDictation()' },
  { icon: 'fa-code-fork', title: 'Worktree 管理', desc: '隔离的 Git 工作树', action: 'FeaturesHub.showWorktreeInfo()' },
];

const SKILL_ACTIONS: QuickAction[] = [
  { icon: 'fa-file-lines', title: '转 Markdown', desc: '-i <文件> PDF/DOCX 转为 Markdown', action: "triggerQuickAction('markitdown -i')" },
  { icon: 'fa-file-word', title: '读取 Word', desc: '-i <文件> 提取 .docx 文本', action: "triggerQuickAction('docx_read -i')" },
  { icon: 'fa-file-pdf', title: '提取 PDF', desc: '-i <文件> 提取 PDF 文本', action: "triggerQuickAction('pdf_extract -i')" },
  { icon: 'fa-file-zipper', title: '压缩打包', desc: '-o <输出> -t <目标> [-p 密码]', action: "triggerQuickAction('archive_compress -o')" },
  { icon: 'fa-box-open', title: '解压文件', desc: '-i <压缩包> [-d 目录] [-p 密码]', action: "triggerQuickAction('archive_extract -i')" },
  { icon: 'fa-list', title: '查看压缩包', desc: '-i <压缩包> 列出内容', action: "triggerQuickAction('archive_list -i')" },
  { icon: 'fa-trash-can', title: '软件卸载', desc: '列出/卸载已安装软件', action: "triggerQuickAction('uninstaller')" },
  { icon: 'fa-music', title: '媒体扫描', desc: '全盘扫描 MP3/WAV/JPG', action: "triggerQuickAction('media_scan')" },
  { icon: 'fa-cloud', title: '云盘管理', desc: 'OneDrive/WebDAV/百度', action: "triggerQuickAction('storage_hub --action list')" },
  { icon: 'fa-radar', title: '端口扫描', desc: '-t <IP> [-p 端口范围]', action: "triggerQuickAction('sec_scan -t')" },
  { icon: 'fa-shield-halved', title: 'Web 安全测试', desc: '-t <URL> [-m recon|scan|full]', action: "triggerQuickAction('web_sec_test -t')" },
  { icon: 'fa-arrows-rotate', title: '格式转换', desc: '-i <输入> -f <docx|epub|png>', action: "triggerQuickAction('format_convert -i')" },
];

function actionGroup(label: string, actions: QuickAction[]): string {
  const cards = actions
    .map(
      (a) => `
        <button type="button" class="quick-action-card" onclick="${a.action}">
          <span class="quick-action-icon"><i class="fas ${a.icon}"></i></span>
          <span class="quick-action-title">${a.title}</span>
          <span class="quick-action-desc">${a.desc}</span>
        </button>`
    )
    .join('');
  return `
    <div class="skill-section-divider"><span>${label}</span></div>
    <div class="quick-actions-container">${cards}</div>`;
}

function pageHeader(title: string, titleId: string, actions: string): string {
  return `
    <header class="page-header">
      <div class="page-heading">
        <span class="page-eyebrow">Butler 工作区</span>
        <h1 class="page-title" id="${titleId}">${title}</h1>
      </div>
      <div class="page-actions">${actions}</div>
    </header>`;
}

export function renderChatPage(): string {
  return `
    <section class="page-cell" id="cell-0-0" data-page="chat">
      ${pageHeader(
        '智能助手',
        'chat-view-title',
        `<div class="status-indicators">
           <span id="connection-status" class="status-dot green active" title="本地服务连接"></span>
           <span id="thinking-status" class="status-dot blue" title="思考中"></span>
         </div>`
      )}
      <div class="page-body">
        <div class="surface-card chat-surface">
          <div id="interaction-flow">
            <div class="welcome-message">
              <h1>今天要处理什么？</h1>
              <p>拖入报错截图、输入指令，或从下方功能开始。</p>
              ${actionGroup('常用', COMMON_ACTIONS)}
              ${actionGroup('应用功能', APP_ACTIONS)}
              ${actionGroup('本地技能', SKILL_ACTIONS)}
            </div>
          </div>
          <div class="chat-composer">
            <div class="chat-input-container">
              <div class="input-actions-left">
                <button class="icon-btn-small" id="voice-toggle-btn" title="语音输入"><i class="fas fa-microphone"></i></button>
                <button class="icon-btn-small" title="更多操作"><i class="fas fa-plus"></i></button>
              </div>
              <div class="input-wrapper">
                <div id="chat-input" contenteditable="true" placeholder="发送消息或拖入截图..."></div>
              </div>
              <div class="input-actions-right">
                <button class="send-btn" id="send-command-btn" title="发送"><i class="fas fa-arrow-up"></i></button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>`;
}

export function renderTimeMachinePage(): string {
  return `
    <section class="page-cell" id="cell-1-0" data-page="timemachine">
      ${pageHeader('时光监控', 'tm-view-title', `<span class="page-meta">系统历史快照与传感器遥测</span>`)}
      <div class="page-body">
        <div class="surface-card tm-card">
          <div class="timemachine-container">
            <div class="metrics-visualizer" id="tm-metrics"></div>
            <div class="history-log-view" id="tm-logs"></div>
            <div class="tm-slider-bar">
              <input type="range" id="global-tm-slider" min="0" max="100" value="100">
              <div class="tm-time-label">现在</div>
            </div>
          </div>
        </div>
      </div>
    </section>`;
}

export function renderDagPage(): string {
  const toolbar = `
    <div class="dag-toolbar">
      <button class="toolbar-btn success" onclick="runDagPipeline()" title="启动流水线"><i class="fas fa-play"></i> 启动</button>
      <button class="toolbar-btn warning" onclick="pauseDagPipeline()" title="暂停流水线"><i class="fas fa-pause"></i> 暂停</button>
      <button class="toolbar-btn danger" onclick="clearDagCanvas()" title="清空画布"><i class="fas fa-trash-alt"></i> 清空</button>
    </div>`;
  return `
    <section class="page-cell" id="cell-0-1" data-page="dag">
      ${pageHeader('任务画布', 'dag-view-title', toolbar)}
      <div class="page-body">
        <div class="surface-card dag-card">
          <div class="dag-canvas" id="workflow-canvas">
            <svg id="dag-svg" style="position:absolute; width:100%; height:100%; pointer-events:none;"></svg>
            <div class="canvas-placeholder">
              <i class="fas fa-diagram-project"></i>
              <h3>拖动技能卡片到此处构建流水线</h3>
            </div>
          </div>
        </div>
      </div>
    </section>`;
}

export function renderSkillsPage(): string {
  const actions = `
    <div class="header-actions">
      <button class="icon-btn-small" onclick="toggleTerminal()" title="打开终端">${icon('terminal', 15)}</button>
      <button class="icon-btn-small" onclick="toggleMemos()" title="备忘录">${icon('note', 15)}</button>
    </div>`;
  return `
    <section class="page-cell" id="cell-1-1" data-page="skills">
      ${pageHeader('技能仓储', 'skills-view-title', actions)}
      <div class="page-body">
        <div class="skills-files-layout">
          <aside class="surface-card skills-drawer-card">
            <div class="panel-subtitle"><i class="fas fa-cubes"></i> 本地技能</div>
            <div class="skills-drawer" id="skills-drawer"></div>
          </aside>
          <section class="surface-card files-card">
            <div class="panel-subtitle"><i class="fas fa-folder-open"></i> 文件</div>
            <div class="files-explorer-mini">
              <div class="files-grid" id="files-list"></div>
            </div>
          </section>
        </div>
      </div>
    </section>`;
}

export function renderAllPages(): string {
  return [renderChatPage(), renderTimeMachinePage(), renderDagPage(), renderSkillsPage()].join('');
}
