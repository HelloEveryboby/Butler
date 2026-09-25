/**
 * Butler 呼吸灯 —— 子界面运行状态指示器（GUI 左上角 / 全屏置顶 HUD）
 *
 * 打开多少个子界面就显示多少颗灯：
 *   - 慢呼吸 : 空闲（窗口开着，没有程序在跑）
 *   - 快闪   : 该界面有程序在运行
 *   - 红色   : 程序异常
 *
 * 状态来源：
 *   1. 后端 butler/core/window_registry.py（独立 OS 窗口 + 任务绑定）→ window.onWindowStates()
 *   2. 主界面内子面板（终端/备忘录/设置…）开合由 MutationObserver 自动上报
 *
 * 无需构建：本文件为纯 JS，直接由 index.html / breath_hud.html 引用。
 */
(function () {
  'use strict';

  // 子面板 DOM id → [注册 id, 显示名]
  const SUBVIEW_MAP = {
    'terminal-overlay': ['view:terminal', '终端'],
    'memos-overlay': ['view:memos', '备忘录'],
    'settings-overlay': ['view:settings', '系统设置'],
  };

  const STATE_TEXT = { idle: '空闲', running: '运行中', error: '异常' };

  class BreathLights {
    constructor() {
      const host = document.getElementById('breath-lights');
      this.mode = (host && host.dataset.mode) || 'inline'; // inline | hud
      this.states = [];
      this._viewOpen = {};
      this._renderPending = false;

      this.container = host || this.createContainer();
      this.container.classList.add(this.mode === 'hud' ? 'breath-lights-hud' : 'breath-lights-inline');

      this.observeSubViews();
      this.hookGlobals();
      this.bindReady();
    }

    createContainer() {
      const el = document.createElement('div');
      el.id = 'breath-lights';
      document.body.appendChild(el);
      return el;
    }

    /* ---------- 后端桥接 ---------- */

    callApi(method, ...args) {
      try {
        const api = window.pywebview && window.pywebview.api;
        if (api && typeof api[method] === 'function') {
          return api[method](...args);
        }
      } catch (e) { /* 呼吸灯永不干扰主流程 */ }
      return null;
    }

    bindReady() {
      const boot = () => {
        this.callApi('breath_light_states')?.then?.((states) => {
          if (Array.isArray(states)) this.setStates(states);
        });
        this.callApi('breath_light_get_mode')?.then?.((mode) => {
          if (mode) this.applyMode(mode);
        });
      };
      if (window.pywebview && window.pywebview.api) {
        boot();
      } else {
        window.addEventListener('pywebviewready', boot, { once: true });
      }
    }

    hookGlobals() {
      // 后端推送子界面状态
      window.onWindowStates = (states) => this.setStates(states || []);
      // 设置面板保存模式（写后端配置；后端回推 applyMode 生效）
      window.setBreathLightMode = (mode) => {
        this.applyMode(mode);
        this.callApi('breath_light_set_mode', mode);
      };
      // 后端回推 / 本地应用显示模式
      window.applyBreathLightMode = (mode) => this.applyMode(mode);
    }

    applyMode(mode) {
      if (!['inline', 'hud', 'off'].includes(mode)) mode = 'inline';
      this.displayMode = mode;
      if (this.mode === 'inline') {
        this.container.style.display = (mode === 'inline') ? 'flex' : 'none';
      }
      const sel = document.getElementById('setting-breath-light-mode');
      if (sel && sel.value !== mode) sel.value = mode;
    }

    /* ---------- 子面板自动上报 ---------- */

    observeSubViews() {
      Object.keys(SUBVIEW_MAP).forEach((elId) => {
        const el = document.getElementById(elId);
        if (!el) return;
        const [viewId, title] = SUBVIEW_MAP[elId];
        const isOpen = () => !el.classList.contains('hidden');
        this.reportView(viewId, title, isOpen());
        try {
          new MutationObserver(() => this.reportView(viewId, title, isOpen()))
            .observe(el, { attributes: true, attributeFilter: ['class'] });
        } catch (e) { /* noop */ }
      });
    }

    reportView(viewId, title, open) {
      if (this._viewOpen[viewId] === open) return;
      this._viewOpen[viewId] = open;
      this.callApi('breath_light_view', viewId, title, open);
    }

    /* ---------- 渲染 ---------- */

    setStates(states) {
      this.states = states;
      if (this._renderPending) return;
      this._renderPending = true;
      requestAnimationFrame(() => {
        this._renderPending = false;
        this.render();
      });
    }

    render() {
      const visible = this.states.filter((s) => (s.transient ? s.state !== 'idle' : true));
      this.container.innerHTML = '';
      visible.forEach((s) => {
        const dot = document.createElement('div');
        dot.className = `breath-dot state-${s.state || 'idle'}`;
        dot.dataset.id = s.id;

        const core = document.createElement('span');
        core.className = 'breath-dot-core';
        dot.appendChild(core);

        const tip = document.createElement('span');
        tip.className = 'breath-tooltip';
        const detail = s.detail ? ` · ${s.detail}` : '';
        const tasks = s.task_count ? ` · ${s.task_count} 个任务` : '';
        tip.textContent = `${s.title || s.id} · ${STATE_TEXT[s.state] || s.state}${tasks}${detail}`;
        dot.appendChild(tip);

        dot.addEventListener('click', () => this.focusEntry(s.id));
        this.container.appendChild(dot);
      });
    }

    focusEntry(id) {
      const res = this.callApi('breath_light_focus', id);
      if (res && typeof res.then === 'function') {
        res.then((r) => this.raiseIfView(r));
      } else {
        this.raiseIfView(res);
      }
    }

    raiseIfView(result) {
      if (!result || result.kind !== 'view') return;
      // view:xxx → dom id
      const elId = Object.keys(SUBVIEW_MAP).find((k) => SUBVIEW_MAP[k][0] === result.view_id);
      const el = elId && document.getElementById(elId);
      if (el) el.classList.remove('hidden');
    }
  }

  if (typeof document !== 'undefined') {
    const start = () => { window.breathLights = new BreathLights(); };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', start, { once: true });
    } else {
      start();
    }
  }
})();
