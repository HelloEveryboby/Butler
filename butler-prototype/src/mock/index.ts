import type { Client, Tool, LogEntry, UsagePoint, ActivityItem } from '../types/index.js';

const now = Date.now();
const hoursAgo = (h: number) => new Date(now - h * 3600000).toISOString();
const daysAgo = (d: number) => new Date(now - d * 86400000).toISOString();

export const clients: Client[] = [
  {
    id: 'c1', name: 'Production API', provider: 'anthropic', model: 'claude-3.7-sonnet-20250219',
    status: 'connected', config: { temperature: 0.7, maxTokens: 4096, topP: 0.9, systemPrompt: 'You are a helpful assistant.' },
    usage: { tokensToday: 184532, requestsToday: 342, costMonth: 2847.52 },
    createdAt: daysAgo(120), lastActive: hoursAgo(0.3),
  },
  {
    id: 'c2', name: 'Analytics Pipeline', provider: 'openai', model: 'gpt-4o-2025-08-01',
    status: 'connected', config: { temperature: 0.3, maxTokens: 8192, topP: 1.0, systemPrompt: 'You are a data analyst assistant.' },
    usage: { tokensToday: 94211, requestsToday: 128, costMonth: 1523.80 },
    createdAt: daysAgo(90), lastActive: hoursAgo(1.2),
  },
  {
    id: 'c3', name: 'Customer Support Bot', provider: 'google', model: 'gemini-2.5-pro',
    status: 'connected', config: { temperature: 0.8, maxTokens: 2048, topP: 0.95, systemPrompt: 'You are a customer service representative.' },
    usage: { tokensToday: 234012, requestsToday: 567, costMonth: 987.45 },
    createdAt: daysAgo(60), lastActive: hoursAgo(0.1),
  },
  {
    id: 'c4', name: 'Code Review Assistant', provider: 'anthropic', model: 'claude-3-5-haiku-20241022',
    status: 'connected', config: { temperature: 0.2, maxTokens: 4096, topP: 0.9, systemPrompt: 'You are a senior code reviewer.' },
    usage: { tokensToday: 45221, requestsToday: 89, costMonth: 412.30 },
    createdAt: daysAgo(45), lastActive: hoursAgo(0.5),
  },
  {
    id: 'c5', name: 'Content Generator', provider: 'openai', model: 'gpt-4o-mini-2024-07-18',
    status: 'disconnected', config: { temperature: 0.9, maxTokens: 4096, topP: 0.95, systemPrompt: 'You are a creative writer.' },
    usage: { tokensToday: 0, requestsToday: 0, costMonth: 234.10 },
    createdAt: daysAgo(30), lastActive: hoursAgo(26.5),
  },
  {
    id: 'c6', name: 'Research Assistant', provider: 'mistral', model: 'mistral-large-2.0',
    status: 'connected', config: { temperature: 0.5, maxTokens: 16384, topP: 0.9, systemPrompt: 'You are a research assistant with access to academic papers.' },
    usage: { tokensToday: 67432, requestsToday: 45, costMonth: 589.20 },
    createdAt: daysAgo(25), lastActive: hoursAgo(2.1),
  },
  {
    id: 'c7', name: 'Translation Service', provider: 'google', model: 'gemini-2.0-flash',
    status: 'connected', config: { temperature: 0.1, maxTokens: 1024, topP: 1.0, systemPrompt: 'You are a professional translator.' },
    usage: { tokensToday: 128910, requestsToday: 892, costMonth: 312.60 },
    createdAt: daysAgo(20), lastActive: hoursAgo(0.8),
  },
  {
    id: 'c8', name: 'Meeting Summarizer', provider: 'openai', model: 'gpt-4.1-2025-03-01',
    status: 'error', config: { temperature: 0.4, maxTokens: 8192, topP: 0.9, systemPrompt: 'You are a meeting summarizer.' },
    usage: { tokensToday: 12400, requestsToday: 18, costMonth: 178.90 },
    createdAt: daysAgo(15), lastActive: hoursAgo(4.5),
  },
  {
    id: 'c9', name: 'Math Tutor', provider: 'custom', model: 'custom-math-70b',
    status: 'connected', config: { temperature: 0.3, maxTokens: 4096, topP: 0.95, systemPrompt: 'You are a patient math tutor.' },
    usage: { tokensToday: 23451, requestsToday: 34, costMonth: 0.00 },
    createdAt: daysAgo(10), lastActive: hoursAgo(1.8),
  },
  {
    id: 'c10', name: 'Data Extractor', provider: 'anthropic', model: 'claude-3-opus-20240229',
    status: 'connected', config: { temperature: 0.1, maxTokens: 2048, topP: 1.0, systemPrompt: 'You are a structured data extraction specialist.' },
    usage: { tokensToday: 56723, requestsToday: 67, costMonth: 1245.00 },
    createdAt: daysAgo(8), lastActive: hoursAgo(0.4),
  },
  {
    id: 'c11', name: 'Chatbot Beta', provider: 'mistral', model: 'mistral-nemo-12b',
    status: 'connected', config: { temperature: 0.7, maxTokens: 2048, topP: 0.9, systemPrompt: 'You are a friendly chatbot.' },
    usage: { tokensToday: 8921, requestsToday: 23, costMonth: 45.60 },
    createdAt: daysAgo(5), lastActive: hoursAgo(3.2),
  },
  {
    id: 'c12', name: 'Legal Document Review', provider: 'openai', model: 'o3-mini-2025-01-31',
    status: 'connected', config: { temperature: 0.05, maxTokens: 16384, topP: 1.0, systemPrompt: 'You are a legal document analysis assistant.' },
    usage: { tokensToday: 34512, requestsToday: 12, costMonth: 678.30 },
    createdAt: daysAgo(3), lastActive: hoursAgo(1.5),
  },
];

export const tools: Tool[] = [
  { id: 't1', name: 'Web Search', description: 'Search the web for real-time information', category: 'search', status: 'enabled', configured: true, usageCount: 1523 },
  { id: 't2', name: 'Code Interpreter', description: 'Execute and analyze code snippets', category: 'code', status: 'enabled', configured: true, usageCount: 892 },
  { id: 't3', name: 'Database Query', description: 'Run read-only SQL queries against connected databases', category: 'data', status: 'enabled', configured: true, usageCount: 445 },
  { id: 't4', name: 'File Reader', description: 'Read and parse files from connected storage', category: 'file', status: 'enabled', configured: true, usageCount: 1203 },
  { id: 't5', name: 'Web Scraper', description: 'Fetch and extract content from web pages', category: 'web', status: 'enabled', configured: true, usageCount: 678 },
  { id: 't6', name: 'Image Generator', description: 'Create and edit images from text descriptions', category: 'custom', status: 'disabled', configured: true, usageCount: 234 },
  { id: 't7', name: 'Calculator', description: 'Precise mathematical computations', category: 'code', status: 'enabled', configured: true, usageCount: 2341 },
  { id: 't8', name: 'Translation Engine', description: 'Translate text between 100+ languages', category: 'custom', status: 'enabled', configured: true, usageCount: 567 },
  { id: 't9', name: 'Data Visualizer', description: 'Create charts and graphs from tabular data', category: 'data', status: 'enabled', configured: false, usageCount: 123 },
  { id: 't10', name: 'PDF Parser', description: 'Extract structured data from PDF documents', category: 'file', status: 'enabled', configured: true, usageCount: 389 },
  { id: 't11', name: 'Git Operations', description: 'Interact with Git repositories', category: 'code', status: 'disabled', configured: true, usageCount: 56 },
  { id: 't12', name: 'Email Sender', description: 'Send emails through connected services', category: 'custom', status: 'enabled', configured: false, usageCount: 12 },
  { id: 't13', name: 'Calendar Reader', description: 'Query calendar events and availability', category: 'data', status: 'enabled', configured: true, usageCount: 234 },
  { id: 't14', name: 'Document Writer', description: 'Generate formatted documents (DOCX, HTML, MD)', category: 'file', status: 'enabled', configured: true, usageCount: 456 },
  { id: 't15', name: 'API Tester', description: 'Send HTTP requests and inspect responses', category: 'web', status: 'disabled', configured: true, usageCount: 89 },
];

const levels: LogEntry['level'][] = ['info', 'warn', 'error', 'debug'];
const sampleMessages = [
  'Completed response generation',
  'Rate limit approached — throttling',
  'API key rotated successfully',
  'Connection timeout after 30s',
  'Token usage exceeded 80% of context window',
  'System prompt updated',
  'Model parameters changed',
  'Request processed in 2.3s',
  'Tool call executed successfully',
  'Fallback model activated',
  'Invalid configuration detected',
  'Usage metrics recorded',
];

export const logs: LogEntry[] = Array.from({ length: 50 }, (_, i) => {
  const level = levels[i % levels.length];
  const clientId = `c${((i % 12) + 1).toString()}`;
  const inputTokens = 500 + Math.floor(Math.random() * 3000);
  const outputTokens = 100 + Math.floor(Math.random() * 2000);
  return {
    id: `l${i + 1}`,
    timestamp: hoursAgo((i * 0.5) + Math.random() * 0.3),
    level,
    clientId,
    message: sampleMessages[i % sampleMessages.length],
    duration: 100 + Math.floor(Math.random() * 4800),
    tokens: { input: inputTokens, output: outputTokens },
    cost: Number(((inputTokens + outputTokens) * 0.000003).toFixed(4)),
  };
});

export const usage: UsagePoint[] = Array.from({ length: 30 }, (_, i) => {
  const date = daysAgo(29 - i);
  const baseTokens = 150000 + Math.floor(Math.random() * 200000);
  const clientBreakdown: Record<string, { tokens: number; cost: number }> = {};
  let totalCost = 0;
  for (let j = 1; j <= 12; j++) {
    const cid = `c${j}`;
    const t = Math.floor(baseTokens * (0.05 + Math.random() * 0.2));
    const c = Number((t * 0.000003).toFixed(2));
    clientBreakdown[cid] = { tokens: t, cost: c };
    totalCost += c;
  }
  return {
    date,
    tokens: baseTokens,
    cost: Number(totalCost.toFixed(2)),
    requests: 200 + Math.floor(Math.random() * 800),
    byClient: clientBreakdown,
  };
});

const activityTypes: ActivityItem['type'][] = ['request', 'config-change', 'error', 'tool-call'];
const activityMessages: Record<ActivityItem['type'], string[]> = {
  request: ['API request completed', 'Batch processing finished', 'Stream response delivered'],
  'config-change': ['Temperature adjusted to 0.5', 'Model switched to gpt-4o', 'System prompt updated', 'Max tokens increased to 8192'],
  error: ['Rate limit hit', 'Authentication failed', 'Timeout on external tool', 'Invalid response format'],
  'tool-call': ['Web Search executed', 'Code Interpreter ran', 'Database queried', 'File parsed successfully'],
};

export const activity: ActivityItem[] = Array.from({ length: 20 }, (_, i) => {
  const type = activityTypes[i % activityTypes.length];
  const clientId = `c${((i % 12) + 1).toString()}`;
  const msgs = activityMessages[type];
  return {
    id: `a${i + 1}`,
    type,
    message: msgs[i % msgs.length],
    clientId,
    timestamp: hoursAgo((i * 1.2) + Math.random() * 0.5),
  };
});