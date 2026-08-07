import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart3,
  DollarSign,
  Activity,
  Clock,
  Download,
  ChevronLeft,
  ChevronRight,
  Search,
} from 'lucide-react';
import { Card, CardBody } from '@/components/ui/Card.js';
import { Button } from '@/components/ui/Button.js';
import { Badge } from '@/components/ui/Badge.js';
import { Input } from '@/components/ui/Input.js';
import { Skeleton } from '@/components/ui/Skeleton.js';
import { StatCard } from '@/components/ui/StatCard.js';
import { EmptyState } from '@/components/ui/EmptyState.js';
import { getUsage, getClients } from '@/api/index.js';
import type { UsagePoint, Client } from '@/types/index.js';

type SortKey = 'date' | 'tokens' | 'cost' | 'requests' | 'avgLatency' | 'topClient';
type SortDir = 'asc' | 'desc';

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toString();
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatFullDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function Usage() {
  const navigate = useNavigate();
  const [timeRange, setTimeRange] = useState<'7D' | '30D' | '90D'>('30D');
  const [selectedClients, setSelectedClients] = useState<string[]>([]);
  const [clientSearch, setClientSearch] = useState('');
  const [clientDropdownOpen, setClientDropdownOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [usageData, setUsageData] = useState<UsagePoint[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [page, setPage] = useState(1);
  const [hoveredBar, setHoveredBar] = useState<number | null>(null);

  const pageSize = 8;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [data, clientList] = await Promise.all([
          getUsage(timeRange === '7D' ? 7 : timeRange === '30D' ? 30 : 90),
          getClients(),
        ]);
        if (!cancelled) {
          setUsageData(data);
          setClients(clientList);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [timeRange]);

  const clientMap = useMemo(() => {
    const m = new Map<string, Client>();
    clients.forEach((c) => m.set(c.id, c));
    return m;
  }, [clients]);

  const filteredData = useMemo(() => {
    if (selectedClients.length === 0) return usageData;
    return usageData.map((point) => {
      const filteredByClient: Record<string, { tokens: number; cost: number }> = {};
      let totalTokens = 0;
      let totalCost = 0;
      let totalRequests = 0;
      for (const cid of selectedClients) {
        const entry = point.byClient[cid];
        if (entry) {
          filteredByClient[cid] = entry;
          totalTokens += entry.tokens;
          totalCost += entry.cost;
          totalRequests += Math.floor(point.requests * (entry.tokens / Math.max(point.tokens, 1)));
        }
      }
      return {
        ...point,
        tokens: totalTokens,
        cost: Number(totalCost.toFixed(2)),
        requests: totalRequests,
        byClient: filteredByClient,
      };
    });
  }, [usageData, selectedClients]);

  const stats = useMemo(() => {
    const totalTokens = filteredData.reduce((sum, d) => sum + d.tokens, 0);
    const totalCost = filteredData.reduce((sum, d) => sum + d.cost, 0);
    const totalRequests = filteredData.reduce((sum, d) => sum + d.requests, 0);
    const avgLatency = 248;
    return {
      totalTokens,
      totalCost: Number(totalCost.toFixed(2)),
      totalRequests,
      avgLatency,
    };
  }, [filteredData]);

  const clientCosts = useMemo(() => {
    const costs = new Map<string, number>();
    for (const point of usageData) {
      for (const [cid, data] of Object.entries(point.byClient)) {
        costs.set(cid, (costs.get(cid) || 0) + data.cost);
      }
    }
    return Array.from(costs.entries())
      .map(([cid, cost]) => ({
        id: cid,
        name: clientMap.get(cid)?.name || cid,
        cost: Number(cost.toFixed(2)),
      }))
      .sort((a, b) => b.cost - a.cost);
  }, [usageData, clientMap]);

  const maxClientCost = useMemo(
    () => clientCosts.reduce((max, c) => Math.max(max, c.cost), 0),
    [clientCosts],
  );

  const sortedData = useMemo(() => {
    const sorted = [...filteredData].sort((a, b) => {
      const dir = sortDir === 'asc' ? 1 : -1;
      switch (sortKey) {
        case 'date':
          return dir * (new Date(a.date).getTime() - new Date(b.date).getTime());
        case 'tokens':
          return dir * (a.tokens - b.tokens);
        case 'cost':
          return dir * (a.cost - b.cost);
        case 'requests':
          return dir * (a.requests - b.requests);
        case 'avgLatency':
          return dir * (250 - 250);
        case 'topClient':
        default:
          return 0;
      }
    });
    return sorted;
  }, [filteredData, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sortedData.length / pageSize));
  const pagedData = useMemo(
    () => sortedData.slice((page - 1) * pageSize, page * pageSize),
    [sortedData, page],
  );

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortKey(key);
        setSortDir('desc');
      }
    },
    [sortKey],
  );

  const toggleClient = useCallback((clientId: string) => {
    setSelectedClients((prev) =>
      prev.includes(clientId) ? prev.filter((c) => c !== clientId) : [...prev, clientId],
    );
  }, []);

  const handleRowClick = useCallback(
    (row: UsagePoint) => {
      const dateStr = new Date(row.date).toISOString().slice(0, 10);
      navigate(`/logs?date=${dateStr}`);
    },
    [navigate],
  );

  const handleExportCSV = useCallback(() => {
    const headers = ['Date', 'Tokens', 'Cost', 'Requests'];
    const rows = filteredData.map((d) => [
      new Date(d.date).toISOString().slice(0, 10),
      d.tokens.toString(),
      d.cost.toFixed(2),
      d.requests.toString(),
    ]);
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `usage-${timeRange.toLowerCase()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [filteredData, timeRange]);

  const maxTokens = useMemo(
    () => filteredData.reduce((max, d) => Math.max(max, d.tokens), 0) || 1,
    [filteredData],
  );

  const filteredClients = useMemo(() => {
    if (!clientSearch) return clients;
    return clients.filter((c) => c.name.toLowerCase().includes(clientSearch.toLowerCase()));
  }, [clients, clientSearch]);

  const chartPoints = useMemo(() => {
    const w = 800;
    const h = 240;
    const padL = 50;
    const padR = 20;
    const padT = 20;
    const padB = 30;
    const chartW = w - padL - padR;
    const chartH = h - padT - padB;
    const n = filteredData.length;
    const barW = Math.max(2, (chartW / n) * 0.6);
    return filteredData.map((d, i) => {
      const x = padL + (i + 0.5) * (chartW / n);
      const barH = (d.tokens / maxTokens) * chartH;
      return {
        x,
        y: padT + chartH - barH,
        w: barW,
        h: barH,
        point: d,
      };
    });
  }, [filteredData, maxTokens]);

  const columns = useMemo(
    () => [
      {
        key: 'date',
        header: 'Date',
        render: (row: UsagePoint) => (
          <span className="font-mono text-[13px] text-text">{formatFullDate(row.date)}</span>
        ),
      },
      {
        key: 'tokens',
        header: 'Tokens',
        render: (row: UsagePoint) => (
          <span className="font-mono text-[13px] text-text">{row.tokens.toLocaleString()}</span>
        ),
      },
      {
        key: 'cost',
        header: 'Cost',
        render: (row: UsagePoint) => (
          <span className="font-mono text-[13px] text-text">${row.cost.toFixed(2)}</span>
        ),
      },
      {
        key: 'requests',
        header: 'Requests',
        render: (row: UsagePoint) => (
          <span className="font-mono text-[13px] text-text">{row.requests.toLocaleString()}</span>
        ),
      },
      {
        key: 'avgLatency',
        header: 'Avg Latency',
        render: () => <span className="font-mono text-[13px] text-text">~248ms</span>,
      },
      {
        key: 'topClient',
        header: 'Top Client',
        render: (row: UsagePoint) => {
          const entries = Object.entries(row.byClient);
          if (entries.length === 0) return <span className="text-text-muted">—</span>;
          const top = entries.reduce((a, b) => (a[1].tokens > b[1].tokens ? a : b));
          const client = clientMap.get(top[0]);
          return (
            <span className="text-[13px] text-text">
              {client?.name || top[0]}{' '}
              <span className="text-text-muted">({formatTokens(top[1].tokens)})</span>
            </span>
          );
        },
      },
    ],
    [clientMap],
  );

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <div className="animate-fade-up">
        <h1 className="font-display text-xl font-semibold tracking-tight text-text">Usage</h1>
        <p className="mt-1 text-sm text-text-muted">
          Monitor token consumption, costs, and performance
        </p>
      </div>

      <div className="animate-fade-up animation-delay-60 flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-md border border-border bg-surface-2 p-0.5">
          {(['7D', '30D', '90D'] as const).map((r) => (
            <button
              key={r}
              onClick={() => {
                setTimeRange(r);
                setPage(1);
              }}
              className={`rounded-[5px] px-3 py-1.5 text-xs font-medium transition-colors ${
                timeRange === r
                  ? 'bg-primary text-bg'
                  : 'text-text-sub hover:text-text'
              }`}
            >
              {r}
            </button>
          ))}
        </div>

        <div className="relative">
          <button
            onClick={() => setClientDropdownOpen((o) => !o)}
            className="flex h-8 items-center gap-2 rounded-md border border-border bg-surface-2 px-3 text-[13px] text-text-sub transition-colors hover:border-border-strong hover:text-text"
          >
            <Search className="h-3.5 w-3.5" />
            <span>Clients</span>
            {selectedClients.length > 0 && (
              <Badge variant="info" className="gap-0.5 px-1.5 py-0 text-[10px]">
                {selectedClients.length}
              </Badge>
            )}
          </button>
          {clientDropdownOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setClientDropdownOpen(false)} />
              <div className="absolute left-0 top-full z-50 mt-1 w-64 rounded-lg border border-border bg-surface shadow-lg">
                <div className="border-b border-border p-2">
                  <Input
                    placeholder="Search clients..."
                    value={clientSearch}
                    onChange={(e) => setClientSearch(e.target.value)}
                    className="h-8"
                  />
                </div>
                <div className="max-h-60 overflow-y-auto p-1">
                  {filteredClients.map((client) => (
                    <label
                      key={client.id}
                      className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-[13px] text-text hover:bg-surface-2"
                    >
                      <input
                        type="checkbox"
                        checked={selectedClients.includes(client.id)}
                        onChange={() => toggleClient(client.id)}
                        className="h-3.5 w-3.5 rounded border-border bg-surface text-primary focus:ring-primary"
                      />
                      <span className="flex-1 truncate">{client.name}</span>
                      <span className="text-[11px] text-text-muted">{client.provider}</span>
                    </label>
                  ))}
                </div>
                {selectedClients.length > 0 && (
                  <div className="border-t border-border p-2">
                    <button
                      onClick={() => setSelectedClients([])}
                      className="w-full rounded-md px-2 py-1 text-xs text-text-muted hover:bg-surface-2 hover:text-text"
                    >
                      Clear all
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        <Button variant="secondary" size="sm" onClick={handleExportCSV} className="ml-auto">
          <Download className="h-3.5 w-3.5" />
          Export CSV
        </Button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="animate-fade-up rounded-lg border border-border bg-surface p-5"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <Skeleton variant="text" className="w-1/3" />
              <Skeleton variant="text" className="mt-3 w-2/3" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="animate-fade-up animation-delay-60">
            <StatCard
              label="Total Tokens"
              value={formatTokens(stats.totalTokens)}
              change={12.5}
              icon={<BarChart3 className="h-4 w-4" />}
            />
          </div>
          <div className="animate-fade-up animation-delay-120">
            <StatCard
              label="Total Cost"
              value={`$${stats.totalCost.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
              change={8.2}
              icon={<DollarSign className="h-4 w-4" />}
            />
          </div>
          <div className="animate-fade-up animation-delay-180">
            <StatCard
              label="Total Requests"
              value={stats.totalRequests.toLocaleString()}
              change={-3.1}
              icon={<Activity className="h-4 w-4" />}
            />
          </div>
          <div className="animate-fade-up animation-delay-240">
            <StatCard
              label="Avg Latency"
              value={`${stats.avgLatency}ms`}
              change={2.4}
              icon={<Clock className="h-4 w-4" />}
            />
          </div>
        </div>
      )}

      <div className="animate-fade-up animation-delay-120">
        <Card className="h-64">
          <CardBody className="h-64">
            <div className="flex h-full flex-col">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-medium text-text">Token Usage Trend</h3>
                <div className="flex items-center gap-3 text-[11px] text-text-muted">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-sm bg-primary" />
                    Tokens
                  </span>
                </div>
              </div>
              {loading ? (
                <div className="flex-1">
                  <Skeleton variant="rectangular" className="h-full w-full" />
                </div>
              ) : (
                <div className="relative flex-1">
                  <svg
                    viewBox="0 0 800 240"
                    className="h-full w-full"
                    preserveAspectRatio="none"
                  >
                    <defs>
                      <linearGradient id="tokenGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
                        <stop offset="100%" stopColor="#10b981" stopOpacity="0.1" />
                      </linearGradient>
                    </defs>
                    {(() => {
                      const w = 800;
                      const h = 240;
                      const padL = 50;
                      const padR = 20;
                      const padT = 20;
                      const padB = 30;
                      const chartW = w - padL - padR;
                      const chartH = h - padT - padB;
                      const n = filteredData.length;
                      const areaPath =
                        chartPoints.length > 0
                          ? `M ${chartPoints[0].x} ${padT + chartH} ` +
                            chartPoints.map((p) => `L ${p.x} ${p.y}`).join(' ') +
                            ` L ${chartPoints[chartPoints.length - 1].x} ${padT + chartH} Z`
                          : '';
                      return (
                        <>
                          {[0, 0.25, 0.5, 0.75, 1].map((pct) => {
                            const y = padT + pct * chartH;
                            const val = Math.round(maxTokens * (1 - pct));
                            return (
                              <g key={pct}>
                                <line
                                  x1={padL}
                                  y1={y}
                                  x2={w - padR}
                                  y2={y}
                                  stroke="#1f1f23"
                                  strokeWidth="1"
                                />
                                <text
                                  x={padL - 8}
                                  y={y + 3}
                                  textAnchor="end"
                                  className="fill-text-muted"
                                  fontSize="10"
                                >
                                  {formatTokens(val)}
                                </text>
                              </g>
                            );
                          })}
                          {areaPath && <path d={areaPath} fill="url(#tokenGrad)" />}
                          {chartPoints.map((p, i) => (
                            <g key={i}>
                              <rect
                                x={p.x - p.w / 2}
                                y={p.y}
                                width={p.w}
                                height={p.h}
                                rx="1"
                                fill="#10b981"
                                opacity={hoveredBar === i ? 1 : 0.7}
                                className="transition-opacity"
                              />
                              <rect
                                x={p.x - p.w / 2 - 4}
                                y={padT}
                                width={p.w + 8}
                                height={chartH}
                                fill="transparent"
                                onMouseEnter={() => setHoveredBar(i)}
                                onMouseLeave={() => setHoveredBar(null)}
                                className="cursor-pointer"
                              />
                            </g>
                          ))}
                          {filteredData.map((d, i) => {
                            const x = padL + (i + 0.5) * (chartW / n);
                            return (
                              <text
                                key={i}
                                x={x}
                                y={h - 10}
                                textAnchor="middle"
                                className="fill-text-muted"
                                fontSize="10"
                              >
                                {formatDate(d.date)}
                              </text>
                            );
                          })}
                        </>
                      );
                    })()}
                  </svg>
                  {hoveredBar !== null && chartPoints[hoveredBar] && (
                    <div
                      className="pointer-events-none absolute z-10 rounded-md border border-border bg-surface px-3 py-2 text-xs shadow-lg"
                      style={{
                        left: `${(chartPoints[hoveredBar].x / 800) * 100}%`,
                        top: '8px',
                        transform: 'translateX(-50%)',
                      }}
                    >
                      <div className="font-medium text-text">
                        {formatFullDate(chartPoints[hoveredBar].point.date)}
                      </div>
                      <div className="mt-1 text-text-muted">
                        Tokens:{' '}
                        <span className="font-mono text-text">
                          {chartPoints[hoveredBar].point.tokens.toLocaleString()}
                        </span>
                      </div>
                      <div className="text-text-muted">
                        Cost:{' '}
                        <span className="font-mono text-text">
                          ${chartPoints[hoveredBar].point.cost.toFixed(2)}
                        </span>
                      </div>
                      <div className="text-text-muted">
                        Requests:{' '}
                        <span className="font-mono text-text">
                          {chartPoints[hoveredBar].point.requests.toLocaleString()}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="animate-fade-up animation-delay-180 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="h-64 lg:col-span-1">
          <CardBody className="h-64">
            <div className="flex h-full flex-col">
              <h3 className="mb-3 text-sm font-medium text-text">Cost by Client</h3>
              {loading ? (
                <div className="flex-1 space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} variant="text" className="w-full" />
                  ))}
                </div>
              ) : (
                <svg viewBox="0 0 400 200" className="h-full w-full">
                  {clientCosts.slice(0, 8).map((client, i) => {
                    const y = 10 + i * 23;
                    const barW = maxClientCost > 0 ? (client.cost / maxClientCost) * 180 : 0;
                    return (
                      <g key={client.id}>
                        <text
                          x="0"
                          y={y + 10}
                          className="fill-text-sub"
                          fontSize="11"
                        >
                          {client.name.length > 18
                            ? client.name.slice(0, 16) + '…'
                            : client.name}
                        </text>
                        <rect
                          x="140"
                          y={y}
                          width={barW}
                          height="14"
                          rx="3"
                          fill="#10b981"
                          opacity="0.6"
                        />
                        <text
                          x={140 + barW + 6}
                          y={y + 10}
                          className="fill-text"
                          fontSize="11"
                        >
                          ${client.cost.toFixed(2)}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              )}
            </div>
          </CardBody>
        </Card>

        <div className="lg:col-span-2">
          <Card>
            <CardBody className="p-0">
              <div className="flex items-center justify-between px-5 py-4">
                <h3 className="text-sm font-medium text-text">Usage Details</h3>
                <div className="flex items-center gap-1">
                  {(['date', 'tokens', 'cost', 'requests'] as SortKey[]).map((key) => (
                    <button
                      key={key}
                      onClick={() => handleSort(key)}
                      className={`rounded-md px-2 py-1 text-[11px] font-medium uppercase tracking-wide transition-colors ${
                        sortKey === key ? 'bg-surface-2 text-text' : 'text-text-muted hover:text-text'
                      }`}
                    >
                      {key}
                      {sortKey === key && (
                        <span className="ml-0.5">{sortDir === 'asc' ? '↑' : '↓'}</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
              {loading ? (
                <div className="space-y-2 px-5 pb-5">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} variant="text" />
                  ))}
                </div>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[13px]">
                      <thead>
                        <tr className="border-t border-b border-border bg-surface-2">
                          {columns.map((col) => (
                            <th
                              key={col.key}
                              className="cursor-pointer px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-text-muted transition-colors hover:text-text"
                              onClick={() => handleSort(col.key as SortKey)}
                            >
                              <span className="inline-flex items-center gap-1">
                                {col.header}
                                {sortKey === col.key && (
                                  <span className="text-[10px]">
                                    {sortDir === 'asc' ? '↑' : '↓'}
                                  </span>
                                )}
                              </span>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {pagedData.map((row) => (
                          <tr
                            key={row.date}
                            onClick={() => handleRowClick(row)}
                            className="cursor-pointer border-b border-border transition-colors hover:bg-surface-2"
                          >
                            {columns.map((col) => (
                              <td key={col.key} className="px-4 py-2.5">
                                {col.render(row)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {pagedData.length === 0 && (
                    <div className="py-8">
                      <EmptyState
                        icon={<BarChart3 className="h-6 w-6" />}
                        title="No usage data"
                        description="Try adjusting your filters or time range."
                      />
                    </div>
                  )}
                  <div className="flex items-center justify-between border-t border-border px-5 py-3">
                    <span className="text-xs text-text-muted">
                      Showing {(page - 1) * pageSize + 1}–
                      {Math.min(page * pageSize, sortedData.length)} of {sortedData.length}
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-text-muted transition-colors hover:border-border-strong hover:text-text disabled:opacity-30"
                      >
                        <ChevronLeft className="h-3.5 w-3.5" />
                      </button>
                      {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                        const p = i + 1;
                        return (
                          <button
                            key={p}
                            onClick={() => setPage(p)}
                            className={`h-7 w-7 rounded-md text-xs transition-colors ${
                              page === p
                                ? 'bg-primary text-bg'
                                : 'border border-border text-text-muted hover:text-text'
                            }`}
                          >
                            {p}
                          </button>
                        );
                      })}
                      <button
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page === totalPages}
                        className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-text-muted transition-colors hover:border-border-strong hover:text-text disabled:opacity-30"
                      >
                        <ChevronRight className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

