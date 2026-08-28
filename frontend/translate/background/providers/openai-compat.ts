/* ============================================================
   OpenAI 兼容翻译（支持 DeepSeek / GPT / 本地 Ollama 等）
   Butler 默认使用 DeepSeek，与主系统保持一致
   ============================================================ */

import { BaseProvider } from './base';
import { LangCode, ProviderId, ProviderConfig } from '../../utils/types';
import { langName } from '../../utils/languages';

export class OpenAICompatProvider extends BaseProvider {
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

  private buildPrompt(from: LangCode, to: LangCode): string {
    return this.prompt
      .replace('{from}', langName(from))
      .replace('{to}', langName(to));
  }

  async translate(text: string, from: LangCode, to: LangCode): Promise<string> {
    const systemPrompt = this.buildPrompt(from, to);

    const resp = await fetch(`${this.endpoint}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: text },
        ],
        temperature: 0.1,
        max_tokens: 4096,
      }),
    });

    if (!resp.ok) {
      const errBody = await resp.text().catch(() => '');
      throw new Error(`OpenAI-compat HTTP ${resp.status}: ${errBody.slice(0, 200)}`);
    }

    const data = await resp.json();
    let result = data?.choices?.[0]?.message?.content?.trim() ?? '';
    // 去除大模型可能加的引号
    if ((result.startsWith('"') && result.endsWith('"')) ||
        (result.startsWith('「') && result.endsWith('」'))) {
      result = result.slice(1, -1);
    }
    return result;
  }

  async translateBatch(texts: string[], from: LangCode, to: LangCode): Promise<string[]> {
    const systemPrompt = this.buildPrompt(from, to);
    // 用编号批量翻译，减少 API 调用
    const numbered = texts.map((t, i) => `[${i}] ${t}`).join('\n\n');
    const userMsg = `请逐条翻译以下文本，保持编号格式不变，每条翻译后空一行：\n\n${numbered}`;

    const resp = await fetch(`${this.endpoint}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userMsg },
        ],
        temperature: 0.1,
        max_tokens: 8192,
      }),
    });

    if (!resp.ok) throw new Error(`OpenAI-compat batch HTTP ${resp.status}`);
    const data = await resp.json();
    const content = data?.choices?.[0]?.message?.content ?? '';

    // 解析编号格式 [0] xxx [1] xxx
    const results: string[] = new Array(texts.length).fill('');
    const lines = content.split(/\n/);
    let currentIdx = -1;
    for (const line of lines) {
      const match = line.match(/^\[(\d+)\]\s*(.*)/);
      if (match) {
        currentIdx = parseInt(match[1]);
        results[currentIdx] = match[2];
      } else if (currentIdx >= 0 && line.trim()) {
        results[currentIdx] += '\n' + line.trim();
      }
    }
    // 填充空项
    for (let i = 0; i < results.length; i++) {
      if (!results[i]) results[i] = texts[i]; // 失败时保留原文
    }
    return results;
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
