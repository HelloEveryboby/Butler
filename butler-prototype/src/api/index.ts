import type { Client, ClientInput, LogEntry, LogFilter, UsagePoint, ActivityItem, Tool } from '../types/index.js';
import { clients as mockClients, tools as mockTools, logs as mockLogs, usage as mockUsage, activity as mockActivity } from '../mock/index.js';

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const jitter = () => 300 + Math.random() * 500;

// TODO: Replace with real API calls when backend is available

export async function getClients(): Promise<Client[]> {
  await delay(jitter());
  return mockClients.map((c) => ({ ...c }));
}

export async function createClient(input: ClientInput): Promise<Client> {
  await delay(jitter());
  const newClient: Client = {
    ...input,
    id: `c${Date.now()}`,
    usage: { tokensToday: 0, requestsToday: 0, costMonth: 0 },
    createdAt: new Date().toISOString(),
    lastActive: new Date().toISOString(),
  };
  mockClients.push(newClient);
  return { ...newClient };
}

export async function updateClient(id: string, input: Partial<ClientInput>): Promise<Client> {
  await delay(jitter());
  const idx = mockClients.findIndex((c) => c.id === id);
  if (idx === -1) throw new Error(`Client ${id} not found`);
  mockClients[idx] = { ...mockClients[idx], ...input, lastActive: new Date().toISOString() };
  return { ...mockClients[idx] };
}

export async function deleteClient(id: string): Promise<void> {
  await delay(jitter());
  const idx = mockClients.findIndex((c) => c.id === id);
  if (idx === -1) throw new Error(`Client ${id} not found`);
  mockClients.splice(idx, 1);
}

export async function getTools(): Promise<Tool[]> {
  await delay(jitter());
  return mockTools.map((t) => ({ ...t }));
}

export async function toggleTool(id: string, status: 'enabled' | 'disabled'): Promise<Tool> {
  await delay(jitter());
  const tool = mockTools.find((t) => t.id === id);
  if (!tool) throw new Error(`Tool ${id} not found`);
  tool.status = status;
  return { ...tool };
}

export async function getLogs(filter?: LogFilter): Promise<LogEntry[]> {
  await delay(jitter());
  let result = [...mockLogs];
  if (filter?.level) result = result.filter((l) => l.level === filter.level);
  if (filter?.clientId) result = result.filter((l) => l.clientId === filter.clientId);
  result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  if (filter?.limit) result = result.slice(0, filter.limit);
  return result;
}

export async function getLogById(id: string): Promise<LogEntry> {
  await delay(jitter());
  const log = mockLogs.find((l) => l.id === id);
  if (!log) throw new Error(`Log ${id} not found`);
  return { ...log };
}

export async function getUsage(days = 30): Promise<UsagePoint[]> {
  await delay(jitter());
  return mockUsage.slice(-days).map((u) => ({ ...u }));
}

export async function getActivity(limit = 20): Promise<ActivityItem[]> {
  await delay(jitter());
  return mockActivity.slice(0, limit).map((a) => ({ ...a }));
}

export async function sendPrompt(clientId: string, messages: { role: string; content: string }[]): Promise<{
  id: string;
  role: 'assistant';
  content: string;
  timestamp: string;
  tokens: number;
}> {
  await delay(600 + Math.random() * 400);
  const lastMsg = messages[messages.length - 1]?.content ?? '';
  const response = `Based on your message "${lastMsg.slice(0, 40)}${lastMsg.length > 40 ? '...' : ''}", here's a detailed response from the Butler client (${clientId}). The model processed your request successfully with context-aware reasoning.`;
  return {
    id: `msg-${Date.now()}`,
    role: 'assistant',
    content: response,
    timestamp: new Date().toISOString(),
    tokens: response.length,
  };
}