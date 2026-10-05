/* ============================================================
   Site Rules — 站点规则引擎
   特定网站的 DOM 选择器适配，优先级高于通用管线
   ------------------------------------------------------------
   Phase 2 扩容：新闻 / 论文 / 社区 / 技术 / 文档 / 邮件 / 会议
   共 30+ 条域名规则；支持用户自定义规则 JSON 导入导出。
   ============================================================ */

import { SiteRule } from '../../utils/types';

/** 站点规则表（按域名匹配，顺序即优先级） */
const SITE_RULES: SiteRule[] = [
  // ---------- 技术社区 ----------
  {
    domain: 'github.com',
    selectors: ['.markdown-body', '.comment-body', '.blob-wrapper', '.readme-box'],
    exclude: ['.file-info', '.commit-tease', 'pre code', '.CodeMirror'],
  },
  {
    domain: 'gitlab.com',
    selectors: ['.md-area', '.md-holder', '.note-text'],
    exclude: ['pre code', '.file-holder'],
  },
  {
    domain: 'stackoverflow.com',
    selectors: ['.post-text', '.comment-body', '.user-info'],
    exclude: ['.post-menu', '.votecell'],
  },
  {
    domain: 'stackexchange.com',
    selectors: ['.post-text', '.comment-body'],
    exclude: ['.post-menu', '.votecell'],
  },
  {
    domain: 'developer.mozilla.org',
    selectors: ['.article', '.section-content'],
    exclude: ['.code-example pre', '.bc-table'],
  },
  {
    domain: 'medium.com',
    selectors: ['article section'],
    exclude: ['pre', 'code'],
  },
  {
    domain: 'dev.to',
    selectors: ['.crayons-article__main', '.comment-body'],
    exclude: ['pre code'],
  },
  {
    domain: 'hashnode.com',
    selectors: ['.blog-content', '.comment-body'],
    exclude: ['pre code'],
  },
  {
    domain: 'news.ycombinator.com',
    selectors: ['.toptext', '.commtext', '.titleline'],
    exclude: ['.score', '.hnhn'],
  },
  {
    domain: 'reddit.com',
    selectors: ['[data-testid="comment"]', '.RichTextJSON-root', '[data-test-id="post-content"]'],
    exclude: ['pre code'],
  },
  {
    domain: 'twitter.com',
    selectors: ['[data-testid="tweetText"]'],
    exclude: [],
  },
  {
    domain: 'x.com',
    selectors: ['[data-testid="tweetText"]'],
    exclude: [],
  },

  // ---------- 技术博客 / 中文社区 ----------
  {
    domain: 'juejin.cn',
    selectors: ['.article-content', '.comment-content'],
    exclude: ['pre code', '.code-block'],
  },
  {
    domain: 'zhuanlan.zhihu.com',
    selectors: ['.Post-RichTextContainer', '.RichContent-inner', '.CommentContent'],
    exclude: ['pre code', '.Post-NormalSub'],
  },
  {
    domain: 'zhihu.com',
    selectors: ['.RichContent-inner', '.CommentContent'],
    exclude: ['pre code'],
  },

  // ---------- 论文 / 学术 ----------
  {
    domain: 'arxiv.org',
    selectors: ['#abs', '.abstract', '.ltx_page_main', '#content'],
    exclude: ['.ltx_equation', 'pre', 'code', '.ltx_bibliography'],
  },
  {
    domain: 'nature.com',
    selectors: ['.c-article-body', '#Abs1-content', '.c-article-section__content'],
    exclude: ['.c-article-metrics', 'pre', 'code', '.c-fig'],
  },
  {
    domain: 'sciencedirect.com',
    selectors: ['.abstract.author', '#body', '.Abstracts'],
    exclude: ['.figure', 'pre', 'code', '.table'],
  },
  {
    domain: 'semanticscholar.org',
    selectors: ['.abstract-text', '.paper-detail-content', '[data-test-id="abstract"]'],
    exclude: ['.citation-count', 'pre', 'code'],
  },
  {
    domain: 'scholar.google.com',
    selectors: ['.gs_rs', '.gs_ri'],
    exclude: ['.gs_fl'],
  },

  // ---------- 新闻 ----------
  {
    domain: 'bbc.com',
    selectors: ['article', '.ssrcss-1pl2zfy-Paragraph'],
    exclude: ['.ssrcss-'],
  },
  {
    domain: 'bbc.co.uk',
    selectors: ['article', '.ssrcss-1pl2zfy-Paragraph'],
    exclude: ['.ssrcss-'],
  },
  {
    domain: 'nytimes.com',
    selectors: ['article', '.StoryBodyCompanionColumn'],
    exclude: ['.ad', '.css-1dbjc4n'],
  },
  {
    domain: 'reuters.com',
    selectors: ['[data-testid="paragraph"]', 'article'],
    exclude: ['.reuters-', 'aside'],
  },
  {
    domain: 'theguardian.com',
    selectors: ['.article-body-commercial-selector', '.dcr-1cvlnc3', 'article'],
    exclude: ['.ad-slot', 'aside'],
  },
  {
    domain: 'wikipedia.org',
    selectors: ['#mw-content-text .mw-parser-output'],
    exclude: ['.reference', '.navbox', '.infobox', 'pre', 'code'],
  },

  // ---------- 文档站点 ----------
  {
    domain: 'docs.python.org',
    selectors: ['.body', '.section'],
    exclude: ['.highlight pre', '.doctest'],
  },
  {
    domain: 'learn.microsoft.com',
    selectors: ['#main .content', '.markdown-heading'],
    exclude: ['pre code', '.code-block'],
  },
  {
    domain: 'cloud.google.com',
    selectors: ['.devsite-article-body'],
    exclude: ['pre code', '.devsite-code-snippet'],
  },
  {
    domain: 'react.dev',
    selectors: ['article', '.markdown'],
    exclude: ['pre code', '.sandpack'],
  },
  {
    domain: 'vuejs.org',
    selectors: ['.content', '.vt-doc'],
    exclude: ['pre code', '.vt-code-group'],
  },
  {
    domain: 'nextjs.org',
    selectors: ['article', '.markdown'],
    exclude: ['pre code', '.code-block'],
  },
  {
    domain: 'readthedocs.io',
    selectors: ['.document .body', '[role="main"] .section'],
    exclude: ['pre code', '.headerlink'],
  },
  {
    domain: 'docusaurus.io',
    selectors: ['.theme-doc-markdown', '.markdown'],
    exclude: ['pre code', '.theme-doc-toc-mobile'],
  },

  // ---------- 邮件 ----------
  {
    domain: 'mail.google.com',
    selectors: ['.a3s.aiL', '.a3s'],
    exclude: ['.gmail_quote', 'pre', 'code', '.adL'],
  },
  {
    domain: 'outlook.live.com',
    selectors: ['[role="document"]', 'div[contenteditable="false"][class*="rps_"]', '.scrollContainer [role="textbox"]'],
    exclude: ['pre', 'code', '[aria-label="附件"]'],
  },
  {
    domain: 'outlook.office.com',
    selectors: ['[role="document"]', 'div[contenteditable="false"][class*="rps_"]'],
    exclude: ['pre', 'code'],
  },
  {
    domain: 'outlook.office365.com',
    selectors: ['[role="document"]', 'div[contenteditable="false"][class*="rps_"]'],
    exclude: ['pre', 'code'],
  },

  // ---------- 购物 / 其他 ----------
  {
    domain: 'amazon.com',
    selectors: ['#productDescription', '#feature-bullets', '.review-text-content'],
    exclude: [],
  },

  // ---------- 通用 fallback ----------
  {
    domain: /.*/,  // 匹配所有
    selectors: ['article', 'main', '[role="main"]', '.content', '.post', '.entry'],
    exclude: ['pre', 'code', 'nav', 'footer', 'header', '.sidebar', '.menu'],
  },
];

/** 内置规则（只读快照，供导出使用） */
export function getBuiltinRules(): SiteRule[] {
  return SITE_RULES.map(r => ({ ...r }));
}

/**
 * 合并内置规则与用户自定义规则。
 * 自定义规则排在内置规则之前（用户优先），通用 fallback 永远垫底。
 */
export function mergeSiteRules(customRules?: SiteRule[]): SiteRule[] {
  const fallback = SITE_RULES[SITE_RULES.length - 1];
  const builtinHead = SITE_RULES.slice(0, -1);
  const custom = (customRules || []).filter(isValidRule);
  return [...custom, ...builtinHead, fallback];
}

/** 校验单条规则（导入时用） */
export function isValidRule(rule: any): rule is SiteRule {
  if (!rule || typeof rule !== 'object') return false;
  if (typeof rule.domain !== 'string' && !(rule.domain instanceof RegExp)) return false;
  if (rule.selectors !== undefined && !Array.isArray(rule.selectors)) return false;
  if (rule.exclude !== undefined && !Array.isArray(rule.exclude)) return false;
  return true;
}

/**
 * 解析用户导入的规则 JSON（纯函数）。
 * 返回 { rules, error }：全部非法时 error 给出原因，不静默失败。
 */
export function parseCustomRules(json: string): { rules: SiteRule[]; error?: string } {
  let data: any;
  try {
    data = JSON.parse(json);
  } catch (e) {
    return { rules: [], error: `JSON 解析失败: ${e}` };
  }
  const arr = Array.isArray(data) ? data : Array.isArray(data?.rules) ? data.rules : null;
  if (!arr) return { rules: [], error: '格式错误：应为规则数组或 {"rules": [...]}' };

  const rules: SiteRule[] = [];
  const invalid: number[] = [];
  arr.forEach((item: any, i: number) => {
    if (isValidRule(item)) {
      rules.push({
        ...item,
        domain: String(item.domain),
        selectors: item.selectors ? item.selectors.map(String) : [],
        exclude: item.exclude ? item.exclude.map(String) : [],
      });
    } else {
      invalid.push(i + 1);
    }
  });

  if (rules.length === 0) {
    return { rules: [], error: `没有可用规则（非法条目：${invalid.join(', ') || '无'}）` };
  }
  return {
    rules,
    error: invalid.length ? `第 ${invalid.join(', ')} 条非法已跳过` : undefined,
  };
}

/** 导出为 JSON 字符串 */
export function serializeCustomRules(rules: SiteRule[]): string {
  return JSON.stringify(
    rules.map(r => ({
      domain: typeof r.domain === 'string' ? r.domain : String(r.domain),
      selectors: r.selectors || [],
      exclude: r.exclude || [],
      insertPosition: r.insertPosition,
    })),
    null,
    2
  );
}

/**
 * 获取当前页面的站点规则
 * @param hostname 主机名
 * @param customRules 用户自定义规则（优先于内置）
 */
export function getSiteRules(hostname: string, customRules?: SiteRule[]): SiteRule | null {
  for (const rule of mergeSiteRules(customRules)) {
    if (typeof rule.domain === 'string') {
      if (hostname.includes(rule.domain)) return rule;
    } else if (rule.domain instanceof RegExp) {
      if (rule.domain.test(hostname)) return rule;
    }
  }
  return null;
}

/**
 * 获取站点专属的翻译选择器
 */
export function getSiteSelectors(hostname: string, customRules?: SiteRule[]): string[] {
  const rule = getSiteRules(hostname, customRules);
  return rule?.selectors || [];
}

/**
 * 获取站点专属的排除选择器
 */
export function getSiteExcludes(hostname: string, customRules?: SiteRule[]): string[] {
  const rule = getSiteRules(hostname, customRules);
  return rule?.exclude || [];
}
