/* ============================================================
   邮件翻译 — Gmail / Outlook Web
   ------------------------------------------------------------
   正文区识别走站点规则引擎（site-rules 中已注册
   mail.google.com / outlook.live.com / outlook.office.com），
   支持「整封翻译 / 仅译选中」两种模式。
   整封翻译：正文段落双语交错注入（不覆盖原文）。
   仅译选中：选中文字 → 浮动气泡显示译文。
   ============================================================ */

import { sendMessage } from '../../utils/messaging';
import { TranslateConfig } from '../../utils/types';
import { injectStyles } from '../styles/styles';
import { walkTextNodes } from '../dom/walker';
import { segmentTexts } from '../dom/segmenter';
import { getSiteSelectors } from '../dom/site-rules';
import { injectBilingual, restoreAll, isTranslated } from '../dom/injector';

/** 邮件站点判定 */
export function isEmailSite(hostname = location.hostname): boolean {
  return /(^|\.)mail\.google\.com$/.test(hostname)
    || /(^|\.)outlook\.(live|office|office365)\.com$/.test(hostname)
    || /(^|\.)outlook\.office\.com$/.test(hostname);
}

/** 邮件正文根元素（优先站点规则，其次平台默认选择器） */
function getEmailBodyRoots(): Element[] {
  const hostname = location.hostname;

  // 站点规则引擎（自定义规则也生效）
  const siteSelectors = getSiteSelectors(hostname);
  const roots: Element[] = [];
  for (const sel of siteSelectors) {
    try {
      document.querySelectorAll(sel).forEach(el => {
        if ((el.textContent || '').trim().length >= 2 && !roots.includes(el)) roots.push(el);
      });
    } catch {
      /* 非法选择器跳过 */
    }
  }
  if (roots.length > 0) return roots;

  // 平台默认兜底
  if (/mail\.google\.com/.test(hostname)) {
    document.querySelectorAll('.a3s.aiL, .a3s').forEach(el => roots.push(el));
  } else {
    document.querySelectorAll('[role="document"], div[contenteditable="false"][class*="rps_"]').forEach(el =>
      roots.push(el)
    );
  }
  return roots;
}

// ---------- 面板 ----------
let panelEl: HTMLDivElement | null = null;

export function removeEmailPanel(): void {
  panelEl?.remove();
  panelEl = null;
}

export function showEmailPanel(config: TranslateConfig): void {
  injectStyles();
  removeEmailPanel();

  if (!isEmailSite()) {
    // 不静默失败：明确提示
    alert(`当前页面不是支持的邮箱（Gmail / Outlook Web）：${location.hostname}`);
    return;
  }

  panelEl = document.createElement('div');
  panelEl.className = 'bt-doc-panel';
  panelEl.style.cssText = `
    position: fixed; top: 20px; right: 20px; z-index: 2147483647; width: 300px;
    background: #fff; border-radius: 12px; box-shadow: 0 8px 40px rgba(0,0,0,0.2);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; overflow: hidden;
  `;

  panelEl.innerHTML = `
    <div style="padding: 14px 16px; border-bottom: 1px solid #f0f0f0; display:flex; justify-content:space-between; align-items:center;">
      <div style="font-size: 15px; font-weight: 700; color: #1a1a1a;">✉️ 邮件翻译</div>
      <button id="bt-email-close" style="background:none;border:none;font-size:18px;cursor:pointer;color:#999;">✕</button>
    </div>
    <div style="padding: 14px 16px;">
      <button id="bt-email-whole" class="bt-email-btn">🌐 整封翻译（双语对照）</button>
      <button id="bt-email-selection" class="bt-email-btn" style="margin-top:8px;">✂️ 仅译选中</button>
      <button id="bt-email-restore" class="bt-email-btn" style="margin-top:8px;">↩ 显示原文</button>
      <div id="bt-email-status" style="margin-top:10px; font-size:12px; color:#888;"></div>
    </div>
    <style>
      .bt-email-btn {
        width: 100%; padding: 9px 12px; border: 1px solid #4a9eff; background: #fff;
        color: #4a9eff; border-radius: 8px; font-size: 13px; cursor: pointer;
      }
      .bt-email-btn:hover { background: #f0f8ff; }
    </style>
  `;

  document.body.appendChild(panelEl);

  const status = (s: string) => {
    const el = panelEl?.querySelector('#bt-email-status') as HTMLElement;
    if (el) el.textContent = s;
  };

  panelEl.querySelector('#bt-email-close')!.addEventListener('click', removeEmailPanel);
  panelEl.querySelector('#bt-email-whole')!.addEventListener('click', () => {
    void translateWholeEmail(config, status);
  });
  panelEl.querySelector('#bt-email-selection')!.addEventListener('click', () => {
    void translateSelectedEmail(config, status);
  });
  panelEl.querySelector('#bt-email-restore')!.addEventListener('click', () => {
    restoreAll();
    status('已恢复原文');
  });
}

/** 整封翻译：正文段落双语交错 */
async function translateWholeEmail(config: TranslateConfig, status: (s: string) => void): Promise<void> {
  const roots = getEmailBodyRoots();
  if (roots.length === 0) {
    status('⚠️ 未识别到邮件正文（页面结构可能已更新），未做任何修改');
    return;
  }

  let total = 0;
  let done = 0;
  for (const root of roots) {
    const textNodes = walkTextNodes(root, config.excludeSelectors);
    const segments = segmentTexts(textNodes);
    if (segments.length === 0) continue;

    const texts = segments.map(s => s.originalText);
    total += texts.length;
    status(`翻译中... ${done}/${total}`);

    const resp = await sendMessage({ type: 'TRANSLATE', texts, to: config.targetLang });
    if (resp.type === 'TRANSLATE_RESULT') {
      segments.forEach((seg, i) => {
        const translated = resp.results[i]?.translated;
        if (translated) {
          injectBilingual(seg, translated, config.bilingualLayout || 'stacked');
        }
      });
    }
    done += texts.length;
    status(`翻译中... ${done}/${total}`);
  }

  if (total === 0) {
    status('⚠️ 正文没有可翻译内容');
    return;
  }
  status(`✅ 整封翻译完成（${total} 段）`);
}

/** 仅译选中：选中文字 → 气泡显示译文 */
async function translateSelectedEmail(config: TranslateConfig, status: (s: string) => void): Promise<void> {
  const selection = window.getSelection();
  const text = selection?.toString().trim();
  if (!text || text.length < 2) {
    status('⚠️ 请先选中要翻译的文字');
    return;
  }

  const range = selection?.getRangeAt(0);
  const rect = range?.getBoundingClientRect();
  status('翻译中...');

  const resp = await sendMessage({ type: 'TRANSLATE', texts: [text], to: config.targetLang });
  if (resp.type !== 'TRANSLATE_RESULT' || !resp.results[0]) {
    status('⚠️ 翻译失败，请检查翻译源配置');
    return;
  }

  const translated = resp.results[0].translated;
  // 气泡展示（复用划词气泡样式）
  document.querySelectorAll('.bt-bubble.bt-email-bubble').forEach(el => el.remove());
  const bubble = document.createElement('div');
  bubble.className = 'bt-bubble bt-email-bubble';
  bubble.style.position = 'absolute';
  bubble.style.top = `${(rect?.bottom ?? 100) + window.scrollY + 8}px`;
  bubble.style.left = `${Math.min(rect?.left ?? 100, window.innerWidth - 340)}px`;
  bubble.innerHTML = `
    <div class="bt-bubble-content"></div>
    <div class="bt-bubble-actions">
      <button class="bt-bubble-copy" title="复制译文">📋</button>
      <button class="bt-bubble-close" title="关闭">✕</button>
    </div>
  `;
  (bubble.querySelector('.bt-bubble-content') as HTMLElement).textContent = translated;
  document.body.appendChild(bubble);
  bubble.querySelector('.bt-bubble-close')?.addEventListener('click', () => bubble.remove());
  bubble.querySelector('.bt-bubble-copy')?.addEventListener('click', () => {
    void navigator.clipboard.writeText(translated);
    bubble.remove();
  });
  setTimeout(() => bubble.remove(), 12000);
  status('✅ 已翻译选中内容');
}

/** 初始化（邮件站点自动挂一个浮动入口按钮） */
export function initEmailTranslate(config: TranslateConfig): void {
  if (!isEmailSite()) return;
  injectStyles();

  const btn = document.createElement('div');
  btn.className = 'bt-floating-ball';
  btn.style.cssText = 'right: 20px; bottom: 80px; font-size: 18px;';
  btn.title = 'Butler 邮件翻译';
  btn.textContent = '✉';
  btn.addEventListener('click', () => showEmailPanel(config));
  document.body.appendChild(btn);
}
