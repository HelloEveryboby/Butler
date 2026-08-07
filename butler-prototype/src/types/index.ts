export interface Client {
  id: string;
  name: string;
  provider: 'anthropic' | 'openai' | 'google' | 'mistral' | 'custom';
  model: string;
  status: 'connected' | 'disconnected' | 'error';
  config: { temperature: number; maxTokens: number; topP: number; systemPrompt: string };
  usage: { tokensToday: number; requestsToday: number; costMonth: number };
  createdAt: string;
  lastActive: string;
}

export interface Tool {
  id: string;
  name: string;
  description: string;
  category: 'search' | 'code' | 'data' | 'file' | 'web' | 'custom';
  status: 'enabled' | 'disabled';
  configured: boolean;
  usageCount: number;
}

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  clientId: string;
  message: string;
  duration: number;
  tokens: { input: number; output: number };
  cost: number;
}

export interface UsagePoint {
  date: string;
  tokens: number;
  cost: number;
  requests: number;
  byClient: Record<string, { tokens: number; cost: number }>;
}

export interface ActivityItem {
  id: string;
  type: 'request' | 'config-change' | 'error' | 'tool-call';
  message: string;
  clientId: string;
  timestamp: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tokens?: number;
}

export type ClientInput = Omit<Client, 'id' | 'usage' | 'createdAt' | 'lastActive'>;

export interface LogFilter {
  level?: 'info' | 'warn' | 'error' | 'debug';
  clientId?: string;
  limit?: number;
}