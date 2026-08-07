import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { Bot, Send, Square, User, Settings2, ChevronDown, X } from 'lucide-react';
import { Card, Badge, Button, Select, Input, Skeleton } from '@/components/ui';
import { getClients, sendPrompt } from '@/api';
import type { Client, ChatMessage } from '@/types';

interface ChatPanelProps {
  client: Client | null;
  messages: ChatMessage[];
  onSend: (content: string) => void;
  loading: boolean;
  onStop: () => void;
  temperature: number;
  maxTokens: number;
  systemPrompt: string;
  onTemperatureChange: (v: number) => void;
  onMaxTokensChange: (v: number) => void;
  onSystemPromptChange: (v: string) => void;
  onClear: () => void;
}

function ChatPanel({
  client,
  messages,
  onSend,
  loading,
  onStop,
  temperature,
  maxTokens,
  systemPrompt,
  onTemperatureChange,
  onMaxTokensChange,
  onSystemPromptChange,
  onClear,
}: ChatPanelProps) {
  const [input, setInput] = useState('');
  const [showSystemPrompt, setShowSystemPrompt] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    onSend(trimmed);
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const sessionTokens = messages.reduce((sum, m) => sum + (m.tokens ?? 0), 0);
  const sessionCost = (sessionTokens * 0.000003).toFixed(4);
  const msgCount = messages.filter((m) => m.role !== 'system').length;

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <Card className="flex items-center gap-3 px-4 py-3">
        <div className="flex flex-1 items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/15">
            <Bot className="h-4 w-4 text-primary" />
          </div>
          <div className="min-w-0 flex-1">
            {client ? (
              <>
                <p className="truncate text-sm font-medium text-text">{client.name}</p>
                <p className="truncate text-xs text-text-muted">{client.model}</p>
              </>
            ) : (
              <>
                <p className="text-sm font-medium text-text-muted">No client selected</p>
                <p className="text-xs text-text-muted">Choose a model above</p>
              </>
            )}
          </div>
        </div>

        <div className="hidden items-center gap-4 md:flex">
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted">Temp</span>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              onChange={(e) => onTemperatureChange(Number(e.target.value))}
              className="h-1 w-24 cursor-pointer appearance-none rounded-full bg-surface-2 accent-primary"
            />
            <span className="w-8 text-right font-mono text-xs text-text-sub">
              {temperature.toFixed(1)}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted">Max</span>
            <Input
              type="number"
              value={maxTokens}
              min={1}
              max={128000}
              onChange={(e) => onMaxTokensChange(Number(e.target.value))}
              className="h-8 w-24"
            />
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowSystemPrompt(!showSystemPrompt)}
            className="gap-1"
          >
            <Settings2 className="h-3.5 w-3.5" />
            System
            <ChevronDown
              className={`h-3 w-3 transition-transform ${showSystemPrompt ? 'rotate-180' : ''}`}
            />
          </Button>
        </div>
      </Card>

      {showSystemPrompt && (
        <Card className="animate-fade-up overflow-hidden">
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <span className="text-xs font-medium text-text-sub">System Prompt</span>
            <Button variant="ghost" size="sm" onClick={() => setShowSystemPrompt(false)}>
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
          <div className="p-4">
            <textarea
              value={systemPrompt}
              onChange={(e) => onSystemPromptChange(e.target.value)}
              placeholder="You are a helpful assistant..."
              className="h-20 w-full resize-none rounded-md border border-border bg-surface-2 p-3 text-[13px] text-text placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
            />
          </div>
        </Card>
      )}

      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {messages.length === 0 && !loading && (
            <div className="flex h-full flex-col items-center justify-center text-center py-12">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-surface-2">
                <Bot className="h-5 w-5 text-text-muted" />
              </div>
              <p className="text-sm text-text-sub">Start a conversation</p>
              <p className="mt-1 text-xs text-text-muted">
                Select a client and send a message to begin testing
              </p>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div
              key={msg.id}
              className={`flex gap-2.5 animate-fade-up ${
                msg.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
              style={{ animationDelay: `${idx * 60}ms` }}
            >
              {msg.role !== 'user' && (
                <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-surface-2">
                  <Bot className="h-3.5 w-3.5 text-primary" />
                </div>
              )}

              <div className={`max-w-[80%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div
                  className={`rounded-lg px-3.5 py-2.5 text-[13px] leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-primary/15 text-text'
                      : msg.role === 'system'
                        ? 'bg-surface-2 text-text-muted italic'
                        : 'bg-surface-2 text-text'
                  }`}
                >
                  {msg.content}
                </div>

                {msg.role === 'assistant' && (
                  <div className="mt-1.5 flex items-center gap-3 px-1 text-[11px] text-text-muted font-mono">
                    <span>{msg.tokens ?? 0} tokens</span>
                    <span>${((msg.tokens ?? 0) * 0.000003).toFixed(4)}</span>
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-surface-2">
                  <User className="h-3.5 w-3.5 text-accent" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-2.5 animate-fade-up">
              <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-surface-2">
                <Bot className="h-3.5 w-3.5 text-primary" />
              </div>
              <div className="rounded-lg bg-surface-2 px-3.5 py-3">
                <div className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-muted [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-muted [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-muted" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="border-t border-border p-4">
          <div className="flex gap-3">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Send a message..."
              rows={1}
              className="flex-1 resize-none rounded-md border border-border bg-surface-2 px-4 py-3 text-[13px] text-text placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
            />
            {loading ? (
              <Button variant="ghost" onClick={onStop} className="gap-2">
                <Square className="h-3.5 w-3.5 fill-current" />
                Stop
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={handleSend}
                disabled={!input.trim() || !client}
                className="gap-2"
              >
                <Send className="h-3.5 w-3.5" />
                Send
              </Button>
            )}
          </div>
        </div>
      </Card>

      <Card className="flex items-center justify-between px-4 py-2">
        <div className="flex items-center gap-6 text-sm text-text-sub">
          <span className="font-mono">{sessionTokens.toLocaleString()} tokens</span>
          <span className="font-mono">${sessionCost}</span>
          <span>{msgCount} messages</span>
        </div>
        <Button variant="ghost" size="sm" onClick={onClear}>
          Clear conversation
        </Button>
      </Card>
    </div>
  );
}

export default function Playground() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [compareMode, setCompareMode] = useState(false);

  const [primaryClient, setPrimaryClient] = useState<Client | null>(null);
  const [secondaryClient, setSecondaryClient] = useState<Client | null>(null);

  const [primaryMessages, setPrimaryMessages] = useState<ChatMessage[]>([]);
  const [secondaryMessages, setSecondaryMessages] = useState<ChatMessage[]>([]);

  const [primaryLoading, setPrimaryLoading] = useState(false);
  const [secondaryLoading, setSecondaryLoading] = useState(false);

  const [primaryTemp, setPrimaryTemp] = useState(0.7);
  const [primaryMaxTokens, setPrimaryMaxTokens] = useState(4096);
  const [primarySystemPrompt, setPrimarySystemPrompt] = useState('You are a helpful assistant.');

  const [secondaryTemp, setSecondaryTemp] = useState(0.7);
  const [secondaryMaxTokens, setSecondaryMaxTokens] = useState(4096);
  const [secondarySystemPrompt, setSecondarySystemPrompt] = useState('You are a helpful assistant.');

  useEffect(() => {
    getClients()
      .then((data) => {
        setClients(data);
        const connected = data.filter((c) => c.status === 'connected');
        if (connected.length > 0) {
          setPrimaryClient(connected[0]);
          if (connected.length > 1) {
            setSecondaryClient(connected[1]);
          }
          setPrimaryTemp(connected[0].config.temperature);
          setPrimaryMaxTokens(connected[0].config.maxTokens);
          setPrimarySystemPrompt(connected[0].config.systemPrompt);
          if (connected[1]) {
            setSecondaryTemp(connected[1].config.temperature);
            setSecondaryMaxTokens(connected[1].config.maxTokens);
            setSecondarySystemPrompt(connected[1].config.systemPrompt);
          }
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const handleSendPrimary = async (content: string) => {
    if (!primaryClient) return;
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    const newMessages = [...primaryMessages, userMsg];
    setPrimaryMessages(newMessages);
    setPrimaryLoading(true);

    try {
      const response = await sendPrompt(primaryClient.id, newMessages);
      const assistantMsg: ChatMessage = {
        id: response.id,
        role: 'assistant',
        content: response.content,
        timestamp: response.timestamp,
        tokens: response.tokens,
      };
      setPrimaryMessages([...newMessages, assistantMsg]);
    } catch {
      setPrimaryMessages(newMessages);
    } finally {
      setPrimaryLoading(false);
    }
  };

  const handleSendSecondary = async (content: string) => {
    if (!secondaryClient) return;
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    const newMessages = [...secondaryMessages, userMsg];
    setSecondaryMessages(newMessages);
    setSecondaryLoading(true);

    try {
      const response = await sendPrompt(secondaryClient.id, newMessages);
      const assistantMsg: ChatMessage = {
        id: response.id,
        role: 'assistant',
        content: response.content,
        timestamp: response.timestamp,
        tokens: response.tokens,
      };
      setSecondaryMessages([...newMessages, assistantMsg]);
    } catch {
      setSecondaryMessages(newMessages);
    } finally {
      setSecondaryLoading(false);
    }
  };

  const handleClearPrimary = () => setPrimaryMessages([]);
  const handleClearSecondary = () => setSecondaryMessages([]);

  if (loading) {
    return (
      <div className="mx-auto flex h-[calc(100vh-56px)] max-w-7xl flex-col gap-6 p-6">
        <div className="space-y-2">
          <Skeleton variant="text" className="h-7 w-48" />
          <Skeleton variant="text" className="w-72" />
        </div>
        <Card className="flex items-center gap-3 px-4 py-3">
          <Skeleton variant="circular" className="h-8 w-8" />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" className="h-4 w-40" />
            <Skeleton variant="text" className="w-56" />
          </div>
        </Card>
        <Card className="flex-1 p-6">
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} variant="text" animationDelay={i * 80} />
            ))}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-56px)] max-w-7xl flex-col gap-4 p-6">
      <div className="animate-fade-up flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-text">Playground</h1>
          <p className="mt-1 text-sm text-text-muted">Test prompts against any Butler client</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-muted">Compare Mode</span>
          <button
            onClick={() => setCompareMode(!compareMode)}
            className={`relative h-5 w-9 rounded-full transition-colors ${
              compareMode ? 'bg-primary' : 'bg-surface-2'
            }`}
          >
            <span
              className={`absolute top-0.5 h-4 w-4 rounded-full bg-text shadow transition-transform ${
                compareMode ? 'translate-x-4' : 'translate-x-0.5'
              }`}
            />
          </button>
        </div>
      </div>

      <div className="animate-fade-up flex items-center gap-3" style={{ animationDelay: '60ms' }}>
        <div className="flex flex-1 items-center gap-3 rounded-lg border border-border bg-surface px-4 py-3">
          <span className="text-xs font-medium text-text-sub">Model</span>
          <Select
            value={primaryClient?.id ?? ''}
            onChange={(e) => {
              const c = clients.find((cl) => cl.id === e.target.value);
              if (c) {
                setPrimaryClient(c);
                setPrimaryTemp(c.config.temperature);
                setPrimaryMaxTokens(c.config.maxTokens);
                setPrimarySystemPrompt(c.config.systemPrompt);
              }
            }}
            className="max-w-xs"
          >
            {clients
              .filter((c) => c.status === 'connected')
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} — {c.model}
                </option>
              ))}
          </Select>
          <div className="flex items-center gap-3 md:hidden">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-text-muted">Temp</span>
              <input
                type="range"
                min={0}
                max={2}
                step={0.1}
                value={primaryTemp}
                onChange={(e) => setPrimaryTemp(Number(e.target.value))}
                className="h-1 w-20 cursor-pointer appearance-none rounded-full bg-surface-2 accent-primary"
              />
              <span className="w-7 text-right font-mono text-xs text-text-sub">
                {primaryTemp.toFixed(1)}
              </span>
            </div>
          </div>
          <Badge variant="info" className="ml-auto">
            {clients.filter((c) => c.status === 'connected').length} connected
          </Badge>
        </div>
      </div>

      {compareMode && (
        <div
          className="animate-fade-up"
          style={{ animationDelay: '120ms' }}
        >
          <Card className="flex items-center gap-3 px-4 py-3">
            <span className="text-xs font-medium text-text-sub">Compare Model</span>
            <Select
              value={secondaryClient?.id ?? ''}
              onChange={(e) => {
                const c = clients.find((cl) => cl.id === e.target.value);
                if (c) {
                  setSecondaryClient(c);
                  setSecondaryTemp(c.config.temperature);
                  setSecondaryMaxTokens(c.config.maxTokens);
                  setSecondarySystemPrompt(c.config.systemPrompt);
                }
              }}
              className="max-w-xs"
            >
              {clients
                .filter((c) => c.status === 'connected')
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} — {c.model}
                  </option>
                ))}
            </Select>
          </Card>
        </div>
      )}

      <div className="flex min-h-0 flex-1 gap-4">
        <div
          className={`animate-fade-up flex min-h-0 flex-1 flex-col ${compareMode ? 'gap-0' : ''}`}
          style={{ animationDelay: compareMode ? '180ms' : '120ms' }}
        >
          <ChatPanel
            client={primaryClient}
            messages={primaryMessages}
            onSend={handleSendPrimary}
            loading={primaryLoading}
            onStop={() => setPrimaryLoading(false)}
            temperature={primaryTemp}
            maxTokens={primaryMaxTokens}
            systemPrompt={primarySystemPrompt}
            onTemperatureChange={setPrimaryTemp}
            onMaxTokensChange={setPrimaryMaxTokens}
            onSystemPromptChange={setPrimarySystemPrompt}
            onClear={handleClearPrimary}
          />
        </div>

        {compareMode && (
          <>
            <div className="w-px bg-border" />
            <div
              className="animate-fade-up flex min-h-0 flex-1 flex-col"
              style={{ animationDelay: '240ms' }}
            >
              <ChatPanel
                client={secondaryClient}
                messages={secondaryMessages}
                onSend={handleSendSecondary}
                loading={secondaryLoading}
                onStop={() => setSecondaryLoading(false)}
                temperature={secondaryTemp}
                maxTokens={secondaryMaxTokens}
                systemPrompt={secondarySystemPrompt}
                onTemperatureChange={setSecondaryTemp}
                onMaxTokensChange={setSecondaryMaxTokens}
                onSystemPromptChange={setSecondarySystemPrompt}
                onClear={handleClearSecondary}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}