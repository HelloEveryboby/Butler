import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Search,
  Download,
  Trash2,
  RefreshCw,
  ChevronDown,
  X,
  Clock,
  Copy,
  ExternalLink,
  Shield,
} from 'lucide-react';
import { Card, CardBody } from '@/components/ui/Card.js';
import { Button } from '@/components/ui/Button.js';
import { Badge } from '@/components/ui/Badge.js';
import { Select } from '@/components/ui/Select.js';
import { Skeleton } from '@/components/ui/Skeleton.js';
import { EmptyState } from '@/components/ui/EmptyState.js';
import { getLogs, getClients } from '@/api/index.js';
import type { LogEntry, Client } from '@/types/index.js';

const levelColors: Record<LogEntry['level'], string> = {
  info: 'bg-sky-500/15 text-sky-400',
  warn: 'bg-amber-500/15 text-amber-400',
  error: 'bg-red-500/15 text-red-400',
  debug: 'bg-zinc-500/15 text-zinc-400',
};

const levelDotColors: Record<LogEntry['level'], string> = {
  info: 'bg-sky-400',
  warn: 'bg-amber-400',
  error: 'bg-red-400',
  debug: 'bg-zinc-400',
};

const levelBadgeVariant: Record<LogEntry['level'], 'info' | 'warning' | 'danger' | 'neutral'> = {
  info: 'info',
  warn: 'warning',
  error: 'danger',
  debug: 'neutral',
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function formatFullTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function formatDuration(ms: number): string {
  if (ms >= 1000) return (ms / 1000).toFixed(2) + 's';
  return ms + 'ms';
}

function formatTokens(n: number): string {
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toString();
}

export default function Logs() {
  const [searchParams] = useSearchParams();
  const dateFilter = searchParams.get('date');

  const [levelFilter, setLevelFilter] = useState<'all' | LogEntry['level']>('all');
  const [selectedClients, setSelectedClients] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(5);
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [showClientDropdown, setShowClientDropdown] = useState(false);
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
  const [newEntryIds, setNewEntryIds] = useState<Set<string>>(new Set());
  const [isRegex, setIsRegex] = useState(false);

  const logContainerRef = useRef<HTMLDivElement>(null);
  const autoRefreshRef = useRef(autoRefresh);

  autoRefreshRef.current = autoRefresh;

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const [data, clientList] = await Promise.all([getLogs(), getClients()]);
      if (dateFilter) {
        setLogs(data);
      } else {
        setLogs(data);
      }
      setClients(clientList);
    } finally {
      setLoading(false);
    }
  }, [dateFilter]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const intervalMs = refreshInterval * 1000;
    const timer = setInterval(async () => {
      const data = await getLogs();
      setLogs((prev) => {
        const existingIds = new Set(prev.map((l) => l.id));
        const newOnes = data.filter((l) => !existingIds.has(l.id));
        if (newOnes.length > 0) {
          setNewEntryIds(new Set(newOnes.map((l) => l.id)));
          setTimeout(() => setNewEntryIds(new Set()), 600);
        }
        return [...newOnes, ...prev].slice(0, 200);
      });
    }, intervalMs);
    return () => clearInterval(timer);
  }, [autoRefresh, refreshInterval]);

  useEffect(() => {
    if (autoRefresh && logContainerRef.current && selectedLog === null) {
      logContainerRef.current.scrollTop = 0;
    }
  }, [logs, autoRefresh, selectedLog]);

  const clientMap = useMemo(() => {
    const m = new Map<string, Client>();
    clients.forEach((c) => m.set(c.id, c));
    return m;
  }, [clients]);

  const filteredLogs = useMemo(() => {
    let result = logs;

    if (dateFilter) {
      result = result.filter((l) => {
        const logDate = new Date(l.timestamp).toISOString().slice(0, 10);
        return logDate === dateFilter;
      });
    }

    if (levelFilter !== 'all') {
      result = result.filter((l) => l.level === levelFilter);
    }

    if (selectedClients.length > 0) {
      result = result.filter((l) => selectedClients.includes(l.clientId));
    }

    if (searchQuery) {
      try {
        if (isRegex) {
          const re = new RegExp(searchQuery, 'i');
          result = result.filter(
            (l) =>
              re.test(l.message) ||
              re.test(l.clientId) ||
              re.test(l.id),
          );
        } else {
          const q = searchQuery.toLowerCase();
          result = result.filter(
            (l) =>
              l.message.toLowerCase().includes(q) ||
              l.clientId.toLowerCase().includes(q) ||
              l.id.toLowerCase().includes(q),
          );
        }
      } catch {
        // regex error — skip filter
      }
    }

    return result;
  }, [logs, dateFilter, levelFilter, selectedClients, searchQuery, isRegex]);

  const toggleClient = useCallback((clientId: string) => {
    setSelectedClients((prev) =>
      prev.includes(clientId) ? prev.filter((c) => c !== clientId) : [...prev, clientId],
    );
  }, []);

  const handleExport = useCallback(() => {
    const headers = ['Timestamp', 'Level', 'Client', 'Message', 'Duration', 'Tokens', 'Cost'];
    const rows = filteredLogs.map((l) => [
      l.timestamp,
      l.level,
      l.clientId,
      l.message,
      l.duration.toString(),
      (l.tokens.input + l.tokens.output).toString(),
      l.cost.toFixed(4),
    ]);
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'logs.csv';
    a.click();
    URL.revokeObjectURL(url);
  }, [filteredLogs]);

  const handleClear = useCallback(() => {
    setLevelFilter('all');
    setSelectedClients([]);
    setSearchQuery('');
  }, []);

  const levelCounts = useMemo(() => {
    return {
      all: logs.length,
      info: logs.filter((l) => l.level === 'info').length,
      warn: logs.filter((l) => l.level === 'warn').length,
      error: logs.filter((l) => l.level === 'error').length,
      debug: logs.filter((l) => l.level === 'debug').length,
    };
  }, [logs]);

  const relatedClientLogs = useMemo(() => {
    if (!selectedLog) return [];
    return logs
      .filter((l) => l.clientId === selectedLog.clientId && l.id !== selectedLog.id)
      .slice(0, 10);
  }, [selectedLog, logs]);

  return (
    <div className="mx-auto flex h-[calc(100vh-56px)] max-w-7xl flex-col p-6">
      <div className="animate-fade-up mb-4">
        <h1 className="font-display text-xl font-semibold tracking-tight text-text">Logs</h1>
        <p className="mt-1 text-sm text-text-muted">Live request and response log</p>
        {dateFilter && (
          <p className="mt-1 text-xs text-text-muted">
            Filtered by date: <span className="font-mono text-text">{dateFilter}</span>
          </p>
        )}
      </div>

      <div className="animate-fade-up animation-delay-60 mb-4">
        <Card>
          <CardBody className="py-3">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-1">
                {(['all', 'info', 'warn', 'error', 'debug'] as const).map((level) => {
                  const isActive = levelFilter === level;
                  const count =
                    level === 'all'
                      ? levelCounts.all
                      : levelCounts[level as LogEntry['level']];
                  return (
                    <button
                      key={level}
                      onClick={() => setLevelFilter(level)}
                      className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                        isActive
                          ? 'bg-surface-2 text-text'
                          : 'text-text-muted hover:bg-surface-2 hover:text-text'
                      }`}
                    >
                      {level !== 'all' && (
                        <span
                          className={`h-1.5 w-1.5 rounded-full ${levelDotColors[level as LogEntry['level']]}`}
                        />
                      )}
                      <span className="capitalize">{level}</span>
                      <span className="rounded bg-surface-2 px-1 py-0.5 text-[10px] text-text-muted">
                        {count}
                      </span>
                    </button>
                  );
                })}
              </div>

              <div className="h-4 w-px bg-border" />

              <div className="relative">
                <button
                  onClick={() => setShowClientDropdown((o) => !o)}
                  className="flex h-7 items-center gap-2 rounded-md border border-border bg-surface-2 px-2.5 text-[13px] text-text-sub transition-colors hover:border-border-strong hover:text-text"
                >
                  <span>Clients</span>
                  {selectedClients.length > 0 && (
                    <Badge variant="info" className="gap-0.5 px-1 py-0 text-[10px]">
                      {selectedClients.length}
                    </Badge>
                  )}
                  <ChevronDown className="h-3 w-3 text-text-muted" />
                </button>
                {showClientDropdown && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setShowClientDropdown(false)}
                    />
                    <div className="absolute left-0 top-full z-50 mt-1 w-56 rounded-lg border border-border bg-surface shadow-lg">
                      <div className="max-h-48 overflow-y-auto p-1">
                        {clients.map((client) => (
                          <label
                            key={client.id}
                            className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-[13px] text-text hover:bg-surface-2"
                          >
                            <input
                              type="checkbox"
                              checked={selectedClients.includes(client.id)}
                              onChange={() => toggleClient(client.id)}
                              className="h-3.5 w-3.5 rounded border-border bg-surface text-primary focus:ring-primary"
                            />
                            <span className="flex-1 truncate">{client.name}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>

              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
                <input
                  type={isRegex ? 'text' : 'text'}
                  placeholder={isRegex ? 'Regex pattern...' : 'Search logs...'}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-7 w-full rounded-md border border-border bg-surface-2 pl-9 pr-20 text-[13px] text-text placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
                />
                <div className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-1">
                  <button
                    onClick={() => setIsRegex((r) => !r)}
                    className={`rounded px-1.5 py-0.5 text-[10px] font-mono transition-colors ${
                      isRegex
                        ? 'bg-primary/20 text-primary'
                        : 'text-text-muted hover:bg-surface hover:text-text'
                    }`}
                    title="Toggle regex mode"
                  >
                    .*
                  </button>
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="flex h-4 w-4 items-center justify-center rounded text-text-muted hover:bg-surface hover:text-text"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </div>
              </div>

              <div className="h-4 w-px bg-border" />

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setAutoRefresh((r) => !r)}
                  className={`flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors ${
                    autoRefresh
                      ? 'border-primary/50 bg-primary/10 text-primary'
                      : 'border-border text-text-muted hover:text-text'
                  }`}
                >
                  <RefreshCw className={`h-3 w-3 ${autoRefresh ? 'animate-spin' : ''}`} />
                  Auto
                </button>
                <Select
                  value={refreshInterval}
                  onChange={(e) => setRefreshInterval(Number(e.target.value))}
                  className="h-7 w-20 text-xs"
                >
                  <option value={3}>3s</option>
                  <option value={5}>5s</option>
                  <option value={10}>10s</option>
                  <option value={30}>30s</option>
                </Select>
              </div>

              <div className="ml-auto flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={handleExport}>
                  <Download className="h-3.5 w-3.5" />
                  Export
                </Button>
                <Button variant="ghost" size="sm" onClick={handleClear}>
                  <Trash2 className="h-3.5 w-3.5" />
                  Clear
                </Button>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="flex items-center border-b border-border bg-surface-2 px-4 py-2">
          <div className="w-28 text-[11px] font-medium uppercase tracking-wide text-text-muted">
            Time
          </div>
          <div className="w-16 text-[11px] font-medium uppercase tracking-wide text-text-muted">
            Level
          </div>
          <div className="w-28 text-[11px] font-medium uppercase tracking-wide text-text-muted">
            Client
          </div>
          <div className="flex-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
            Message
          </div>
          <div className="w-20 text-right text-[11px] font-medium uppercase tracking-wide text-text-muted">
            Duration
          </div>
          <div className="w-16 text-right text-[11px] font-medium uppercase tracking-wide text-text-muted">
            Tokens
          </div>
          <div className="w-16 text-right text-[11px] font-medium uppercase tracking-wide text-text-muted">
            Cost
          </div>
        </div>

        <div
          ref={logContainerRef}
          className="flex-1 overflow-y-auto font-mono text-xs"
        >
          {loading ? (
            <div className="p-4">
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} className="flex gap-4 py-1.5">
                  <Skeleton variant="text" className="w-24" />
                  <Skeleton variant="text" className="w-12" />
                  <Skeleton variant="text" className="w-20" />
                  <Skeleton variant="text" className="flex-1" />
                </div>
              ))}
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="flex-1">
              <EmptyState
                icon={<Search className="h-6 w-6" />}
                title="No logs match your filter"
                description="Try adjusting your search criteria or clearing filters."
                action={
                  <Button variant="secondary" size="sm" onClick={handleClear}>
                    Clear filters
                  </Button>
                }
              />
            </div>
          ) : (
            filteredLogs.map((log, idx) => {
              const isNew = newEntryIds.has(log.id);
              return (
                <div
                  key={log.id}
                  onClick={() => setSelectedLog(log)}
                  className={`flex cursor-pointer items-center border-b border-border/40 px-4 py-1.5 transition-colors ${
                    idx % 2 === 0 ? 'bg-surface' : 'bg-surface/50'
                  } hover:bg-surface-2 ${isNew ? 'animate-fade-up' : ''}`}
                >
                  <div className="w-28 flex-shrink-0 text-text-muted">
                    {formatTimestamp(log.timestamp)}
                  </div>
                  <div className="w-16 flex-shrink-0">
                    <Badge
                      variant={levelBadgeVariant[log.level]}
                      dot
                      className={levelColors[log.level]}
                    >
                      <span className="uppercase">{log.level}</span>
                    </Badge>
                  </div>
                  <div className="w-28 flex-shrink-0 truncate">
                    <span className="text-accent">
                      {clientMap.get(log.clientId)?.name || log.clientId}
                    </span>
                  </div>
                  <div className="flex-1 truncate text-text">{log.message}</div>
                  <div className="w-20 flex-shrink-0 text-right text-text-muted">
                    {formatDuration(log.duration)}
                  </div>
                  <div className="w-16 flex-shrink-0 text-right text-text-muted">
                    {formatTokens(log.tokens.input + log.tokens.output)}
                  </div>
                  <div className="w-16 flex-shrink-0 text-right text-text-muted">
                    ${log.cost.toFixed(4)}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="flex items-center justify-between border-t border-border px-4 py-2 text-[11px] text-text-muted">
          <span>
            Showing {filteredLogs.length} of {logs.length} entries
          </span>
          <span className="flex items-center gap-3">
            {autoRefresh && (
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
                Auto-refreshing every {refreshInterval}s
              </span>
            )}
            <span>Memory: {Math.round(filteredLogs.length * 2.3)}KB</span>
          </span>
        </div>
      </Card>

      {selectedLog && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
            onClick={() => setSelectedLog(null)}
          />
          <div className="fixed right-0 top-0 z-50 flex h-full w-[480px] flex-col border-l border-border bg-surface shadow-2xl">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-text-muted" />
                <h2 className="font-display text-base font-semibold text-text">Log Detail</h2>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-surface-2 hover:text-text"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto">
              <div className="space-y-5 p-5">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={levelBadgeVariant[selectedLog.level]}
                    dot
                    className={levelColors[selectedLog.level]}
                  >
                    <span className="uppercase">{selectedLog.level}</span>
                  </Badge>
                  <span className="font-mono text-xs text-text-muted">{selectedLog.id}</span>
                </div>

                <div className="rounded-lg border border-border bg-surface-2 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-xs font-medium text-text-muted">Timestamp</span>
                    <button className="text-text-muted transition-colors hover:text-text">
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <span className="font-mono text-sm text-text">
                    {formatFullTimestamp(selectedLog.timestamp)}
                  </span>
                </div>

                <div className="rounded-lg border border-border bg-surface-2 p-4">
                  <span className="mb-2 block text-xs font-medium text-text-muted">Client</span>
                  <div className="flex items-center gap-2">
                    <Shield className="h-3.5 w-3.5 text-accent" />
                    <span className="text-sm text-text">
                      {clientMap.get(selectedLog.clientId)?.name || selectedLog.clientId}
                    </span>
                  </div>
                </div>

                <div className="rounded-lg border border-border bg-surface-2 p-4">
                  <span className="mb-2 block text-xs font-medium text-text-muted">Message</span>
                  <p className="text-sm text-text">{selectedLog.message}</p>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="rounded-lg border border-border bg-surface-2 p-3">
                    <span className="mb-1 block text-[11px] text-text-muted">Duration</span>
                    <span className="font-mono text-sm text-text">
                      {formatDuration(selectedLog.duration)}
                    </span>
                  </div>
                  <div className="rounded-lg border border-border bg-surface-2 p-3">
                    <span className="mb-1 block text-[11px] text-text-muted">Tokens</span>
                    <span className="font-mono text-sm text-text">
                      {formatTokens(selectedLog.tokens.input + selectedLog.tokens.output)}
                    </span>
                  </div>
                  <div className="rounded-lg border border-border bg-surface-2 p-3">
                    <span className="mb-1 block text-[11px] text-text-muted">Cost</span>
                    <span className="font-mono text-sm text-text">${selectedLog.cost.toFixed(4)}</span>
                  </div>
                </div>

                <div className="rounded-lg border border-border bg-surface-2 p-4">
                  <span className="mb-2 block text-xs font-medium text-text-muted">
                    Token Breakdown
                  </span>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-text-muted">Input</span>
                      <span className="font-mono text-xs text-text">
                        {selectedLog.tokens.input.toLocaleString()}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-text-muted">Output</span>
                      <span className="font-mono text-xs text-text">
                        {selectedLog.tokens.output.toLocaleString()}
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-border">
                      <div
                        className="h-full bg-primary/60"
                        style={{
                          width: `${(selectedLog.tokens.input / Math.max(selectedLog.tokens.input + selectedLog.tokens.output, 1)) * 100}%`,
                        }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[10px] text-text-muted">
                      <span>Input</span>
                      <span>Output</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-border bg-surface-2 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-medium text-text-muted">Request Payload</span>
                    <button className="text-text-muted transition-colors hover:text-text">
                      <Copy className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <pre className="overflow-x-auto rounded-md bg-bg p-3 font-mono text-[11px] text-text-sub">
{JSON.stringify(
  {
    id: selectedLog.id,
    clientId: selectedLog.clientId,
    message: selectedLog.message,
    timestamp: selectedLog.timestamp,
  },
  null,
  2,
)}
                  </pre>
                </div>

                <div className="rounded-lg border border-border bg-surface-2 p-4">
                  <span className="mb-2 block text-xs font-medium text-text-muted">Response Snippet</span>
                  <pre className="overflow-x-auto rounded-md bg-bg p-3 font-mono text-[11px] text-text-sub">
{JSON.stringify(
  {
    content: '[Truncated response content]',
    model: clientMap.get(selectedLog.clientId)?.model ?? 'unknown',
    usage: {
      inputTokens: selectedLog.tokens.input,
      outputTokens: selectedLog.tokens.output,
    },
  },
  null,
  2,
)}
                  </pre>
                </div>

                {relatedClientLogs.length > 0 && (
                  <div className="rounded-lg border border-border bg-surface-2 p-4">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-xs font-medium text-text-muted">
                        Related Requests
                      </span>
                      <button className="flex items-center gap-1 text-[11px] text-accent transition-colors hover:text-accent/80">
                        View all <ExternalLink className="h-3 w-3" />
                      </button>
                    </div>
                    <div className="space-y-1">
                      {relatedClientLogs.map((l) => (
                        <button
                          key={l.id}
                          onClick={() => setSelectedLog(l)}
                          className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left transition-colors hover:bg-bg"
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${levelDotColors[l.level]}`}
                            />
                            <span className="truncate text-xs text-text">{l.message}</span>
                          </div>
                          <span className="font-mono text-[10px] text-text-muted">
                            {formatTimestamp(l.timestamp)}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}