/* ============================================================
   Site Rules — 站点规则引擎
   特定网站的 DOM 选择器适配，优先级高于通用管线
   从沉浸式翻译开源项目提取的核心站点规则
   ============================================================ */

import { SiteRule } from '../../utils/types';

/** 站点规则表（按域名匹配） */
const SITE_RULES: SiteRule[] = [
  // ---------- 技术社区 ----------
  {
    domain: 'github.com',
    selectors: ['.markdown-body', '.comment-body', '.blob-wrapper', '.readme-box'],
    exclude: ['.file-info', '.commit-tease', 'pre code', '.CodeMirror'],
  },
  {
    domain: 'stackoverflow.com',
    selectors: ['.post-text', '.comment-body', '.user-info'],
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

  // ---------- 新闻 / 博客 ----------
  {
    domain: 'nytimes.com',
    selectors: ['article', '.StoryBodyCompanionColumn'],
    exclude: ['.ad', '.css-1dbjc4n'],
  },
  {
    domain: 'bbc.com',
    selectors: ['article', '.ssrcss-1pl2zfy-Paragraph'],
    exclude: ['.ssrcss-'],
  },
  {
    domain: 'wikipedia.org',
    selectors: ['#mw-content-text .mw-parser-output'],
    exclude: ['.reference', '.navbox', '.infobox', 'pre', 'code'],
  },
  {
    domain: 'reddit.com',
    selectors: ['[data-testid="comment"]', '.RichTextJSON-root'],
    exclude: ['pre code'],
  },

  // ---------- 社交 / 论坛 ----------
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

  // ---------- 购物 ----------
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

/**
 * 获取当前页面的站点规则
 */
export function getSiteRules(hostname: string): SiteRule | null {
  for (const rule of SITE_RULES) {
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
export function getSiteSelectors(hostname: string): string[] {
  const rule = getSiteRules(hostname);
  return rule?.selectors || [];
}

/**
 * 获取站点专属的排除选择器
 */
export function getSiteExcludes(hostname: string): string[] {
  const rule = getSiteRules(hostname);
  return rule?.exclude || [];
}
