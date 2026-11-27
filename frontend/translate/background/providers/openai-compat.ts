/* ============================================================
   OpenAI 兼容翻译（支持 DeepSeek / GPT / 本地 Ollama 等）
   Butler 默认使用 DeepSeek，与主系统保持一致
   ============================================================ */

import { BaseProvider } from './base';
import { LangCode, ProviderId, ProviderConfig, TranslateOptions } from '../../utils/types';
import { langName } from '../../utils/languages';
import { buildSystemPrompt } from '../prompt';
import { LlmCaller } from '../ctx';

export class OpenAICompatProvider extends BaseProvider implements LlmCaller {
  readonly id: ProviderId = 'openai-compat';
  readonly name: string;

  private endpoint: string;
  private apiKey: string;
  private model: string;
  private prompt: string;

  constructor(config: ProviderConfig) {
    super();
    this.name = config.name || 'OpenAI 兼容';
    this.endpoint = config.endpoint || 'https://api.deepseek.com/v1';
    this.apiKey = config.apiKey || '';
    this.model = config.model || 'deepseek-chat';
    this.prompt = config.prompt || '请将以下{from}文本翻译为{to}，只输出译文，不要解释、不要加引号、不要附加任何其他内容。';
  }

  private buildPrompt(from: LangCode, to: LangCode, opts?: TranslateOptions): string {
    // 术语进 prompt + 页内上下文 + 行业预设（事后仍由 applyGlossary 兜底）
    return buildSystemPrompt(this.prompt, langName(from), langName(to), opts);
  }

  /** 通用 LLM 调用（供 AI 上下文摘要等非翻译任务使用） */
  async complete(system: string, user: string): Promise<string> {
    const content = await this.chat([
      { role: 'system', content: system },
      { role: 'user', content: user },
    ], 2048);
    return content;
  }

  /** 底层 chat/completions 调用 */
  private async chat(
    messages: Array<{ role: string; content: string }>,
    maxTokens: number
  ): Promise<string> {
    const resp = await fetch(`${this.endpoint}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        messages,
        temperature: 0.1,
        max_tokens: maxTokens,
      }),
    });

    if (!resp.ok) {
      const errBody = await resp.text().catch(() => '');
      throw new Error(`OpenAI-compat HTTP ${resp.status}: ${errBody.slice(0, 200)}`);
    }

    const data = await resp.json();
    return data?.choices?.[0]?.message?.content ?? '';
  }

  async translate(text: string, from: LangCode, to: LangCode, opts?: TranslateOptions): Promise<string> {
    const systemPrompt = this.buildPrompt(from, to, opts);

    let result = (await this.chat([
      { role: 'system', content: systemPrompt },
      { role: 'user', content: text },
    ], 4096)).trim();
    // 去除大模型可能加的引号
    if ((result.startsWith('"') && result.endsWith('"')) ||
        (result.startsWith('「') && result.endsWith('」'))) {
      result = result.slice(1, -1);
    }
    return result;
  }

  async translateBatch(texts: string[], from: LangCode, to: LangCode, opts?: TranslateOptions): Promise<string[]> {
    const systemPrompt = this.buildPrompt(from, to, opts);
    // 用编号批量翻译，减少 API 调用
    const numbered = texts.map((t, i) => `[${i}] ${t}`).join('\n\n');
    const userMsg = `请逐条翻译以下文本，保持编号格式不变，每条翻译后空一行：\n\n${numbered}`;

    const content = await this.chat([
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userMsg },
    ], 8192);

    // 解析编号格式 [0] xxx [1] xxx，严格校验索引范围，忽略越界/重复
    const results: Array<string | null> = new Array(texts.length).fill(null);
    const lines = content.split(/\n/);
    let currentIdx = -1;
    for (const line of lines) {
      const match = line.match(/^\[(\d+)\]\s*(.*)/);
      if (match) {
        const idx = parseInt(match[1], 10);
        currentIdx = idx >= 0 && idx < texts.length ? idx : -1;
        if (currentIdx >= 0) {
          if (results[currentIdx] === null) results[currentIdx] = match[2];
          else results[currentIdx] = results[currentIdx] + '\n' + match[2];
        }
      } else if (currentIdx >= 0 && line.trim()) {
        results[currentIdx] = (results[currentIdx] ?? '') + '\n' + line.trim();
      }
    }

    // 缺失/空结果单独重试；仍失败则抛错交给降级链/二分重试，
    // 绝不把原文静默回填成「译文」。
    await Promise.all(results.map(async (value, i) => {
      if (value && value.trim()) return;
      const single = await this.translate(texts[i], from, to, opts);
      if (!single || !single.trim()) {
        throw new Error(`批量翻译缺少第 ${i} 条结果，且单条重试返回空`);
      }
      results[i] = single;
    }));

    return results.map((r, i) => r ?? texts[i]);
  }
}

/** DeepSeek 专用 Provider（与 Butler 主系统一致） */
export class DeepSeekProvider extends OpenAICompatProvider {
  constructor(apiKey?: string) {
    super({
      id: 'deepseek-default',
      type: 'openai-compat',
      name: 'DeepSeek（默认）',
      endpoint: 'https://api.deepseek.com/v1',
      apiKey: apiKey || '',
      model: 'deepseek-chat',
      enabled: true,
    });
  }
}
