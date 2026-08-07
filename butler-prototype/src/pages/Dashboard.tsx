import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Zap,
  Coins,
  Wallet,
  RefreshCw,
  Server,
  Wrench,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import { getClients, getActivity, getUsage } from '@/api';
import type { Client, ActivityItem, UsagePoint } from '@/types';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StatCard } from '@/components/ui/StatCard';
import { Skeleton } from '@/components/ui/Skeleton';

function formatRelativeTime(isoDate: string): string {
  const now = Date.now();
  const then = new Date(isoDate).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

function formatNumber(n: number): string {
  return n.toLocaleString();
}

function formatCurrency(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const activityTypeConfig: Record<ActivityItem['type'], { icon: React.ElementType; label: string; variant: 'info' | 'success' | 'danger' | 'warning' | 'neutral' }> = {
  request: { icon: Zap, label: 'Request', variant: 'info' },
  'config-change': { icon: Sparkles, label: 'Config', variant: 'warning' },
  error: { icon: AlertTriangle, label: 'Error', variant: 'danger' },
  'tool-call': { icon: Wrench, label: 'Tool', variant: 'success' },
};

function Dashboard() {
  const navigate = useNavigate();
  const [clients, setClients] = useState<Client[] | null>(null);
  const [activity, setActivity] = useState<ActivityItem[] | null>(null);
  const [usage, setUsage] = useState<UsagePoint[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    setRefreshing(true);
    try {
      const [c, a, u] = await Promise.all([
        getClients(),
        getActivity(20),
        getUsage(7),
      ]);
      setClients(c);
      setActivity(a);
      setUsage(u);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const isLoading = !clients || !activity || !usage;

  const connectedClients = clients?.filter((c) => c.status === 'connected') ?? [];
  const totalRequests = clients?.reduce((sum, c) => sum + c.usage.requestsToday, 0) ?? 0;
  const totalTokens = clients?.reduce((sum, c) => sum + c.usage.tokensToday, 0) ?? 0;
  const totalCost = clients?.reduce((sum, c) => sum + c.usage.costMonth, 0) ?? 0;

  const topClients = connectedClients.slice(0, 5);

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      {/* Page Header */}
      <div className="animate-fade-up flex items-start justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-text">Dashboard</h1>
          <p className="mt-1 text-sm text-text-muted">
            Welcome back. Here&apos;s what&apos;s happening with your Butler clients.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={loadData} loading={refreshing}>
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="animate-fade-up">
          {isLoading ? (
            <div className="rounded-lg border border-border bg-surface p-5">
              <Skeleton variant="text" className="w-24" />
              <Skeleton variant="text" className="mt-3 w-16" />
            </div>
          ) : (
            <StatCard
              label="Active Clients"
              value={`${connectedClients.length}/${clients!.length}`}
              change={2.0}
              icon={<Activity className="h-4 w-4" />}
            />
          )}
        </div>
        <div className="animate-fade-up animation-delay-60">
          {isLoading ? (
            <div className="rounded-lg border border-border bg-surface p-5">
              <Skeleton variant="text" className="w-24" />
              <Skeleton variant="text" className="mt-3 w-16" />
            </div>
          ) : (
            <StatCard
              label="Requests Today"
              value={formatNumber(totalRequests)}
              change={18.0}
              icon={<Zap className="h-4 w-4" />}
            />
          )}
        </div>
        <div className="animate-fade-up animation-delay-120">
          {isLoading ? (
            <div className="rounded-lg border border-border bg-surface p-5">
              <Skeleton variant="text" className="w-24" />
              <Skeleton variant="text" className="mt-3 w-16" />
            </div>
          ) : (
            <StatCard
              label="Tokens Used"
              value={formatNumber(totalTokens)}
              change={7.3}
              icon={<Coins className="h-4 w-4" />}
            />
          )}
        </div>
        <div className="animate-fade-up animation-delay-180">
          {isLoading ? (
            <div className="rounded-lg border border-border bg-surface p-5">
              <Skeleton variant="text" className="w-24" />
              <Skeleton variant="text" className="mt-3 w-16" />
            </div>
          ) : (
            <StatCard
              label="Cost This Month"
              value={formatCurrency(totalCost)}
              change={-2.1}
              icon={<Wallet className="h-4 w-4" />}
            />
          )}
        </div>
      </div>

      {/* Two-column grid */}
      <div className="grid grid-cols-2 gap-4">
        {/* Active Clients */}
        <div className="animate-fade-up animation-delay-60">
          <Card>
            <CardHeader>
              <h2 className="font-display text-sm font-semibold text-text">Active Clients</h2>
              <Button variant="ghost" size="sm" onClick={() => navigate('/clients')}>
                View all
              </Button>
            </CardHeader>
            <CardBody className="p-0">
              {isLoading ? (
                <div className="divide-y divide-border">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="flex items-center gap-3 px-5 py-3.5">
                      <Skeleton variant="circular" className="h-8 w-8" />
                      <div className="flex-1 space-y-2">
                        <Skeleton variant="text" className="w-1/3" />
                        <Skeleton variant="text" className="w-1/4" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {topClients.map((client) => (
                    <li
                      key={client.id}
                      className="group flex cursor-pointer items-center gap-3 px-5 py-3.5 transition-colors hover:bg-surface-2"
                      onClick={() => navigate('/clients')}
                    >
                      <div className="relative flex h-8 w-8 items-center justify-center rounded-md bg-surface-2">
                        <Server className="h-4 w-4 text-text-sub" />
                        <span
                          className={`absolute -right-0.5 -bottom-0.5 h-2 w-2 rounded-full ring-2 ring-surface ${
                            client.status === 'connected'
                              ? 'bg-primary'
                              : client.status === 'error'
                                ? 'bg-danger'
                                : 'bg-text-muted'
                          }`}
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-medium text-text">{client.name}</p>
                        <p className="truncate text-xs text-text-muted">{client.model}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-[13px] font-medium text-text">{client.usage.requestsToday}</p>
                        <p className="text-xs text-text-muted">requests</p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>

        {/* Recent Activity */}
        <div className="animate-fade-up animation-delay-120">
          <Card>
            <CardHeader>
              <h2 className="font-display text-sm font-semibold text-text">Recent Activity</h2>
            </CardHeader>
            <CardBody className="p-0">
              {isLoading ? (
                <div className="divide-y divide-border">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="flex items-start gap-3 px-5 py-3.5">
                      <Skeleton variant="circular" className="h-7 w-7" />
                      <div className="flex-1 space-y-2">
                        <Skeleton variant="text" className="w-4/5" />
                        <Skeleton variant="text" className="w-1/3" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <ul className="max-h-[320px] divide-y divide-border overflow-y-auto">
                  {activity!.slice(0, 8).map((item) => {
                    const config = activityTypeConfig[item.type];
                    const TypeIcon = config.icon;
                    const client = clients!.find((c) => c.id === item.clientId);
                    return (
                      <li key={item.id} className="flex items-start gap-3 px-5 py-3.5">
                        <div className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-surface-2">
                          <TypeIcon className="h-3.5 w-3.5 text-text-sub" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <Badge variant={config.variant} className="text-[10px]">
                              {config.label}
                            </Badge>
                            <span className="truncate text-[13px] text-text">{item.message}</span>
                          </div>
                          <p className="mt-1 text-xs text-text-muted">
                            {client?.name ?? item.clientId} · {formatRelativeTime(item.timestamp)}
                          </p>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>
      </div>

      {/* Token Usage Chart */}
      <div className="animate-fade-up animation-delay-180">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <h2 className="font-display text-sm font-semibold text-text">Token Usage (Last 7 Days)</h2>
            </div>
            <div className="flex items-center gap-4 text-xs text-text-muted">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-primary" /> Tokens
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-accent" /> Requests
              </span>
            </div>
          </CardHeader>
          <CardBody>
            {isLoading ? (
              <Skeleton variant="rectangular" className="h-48" />
            ) : (
              <TokenChart data={usage!} />
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function TokenChart({ data }: { data: UsagePoint[] }) {
  const maxTokens = Math.max(...data.map((d) => d.tokens));
  const maxRequests = Math.max(...data.map((d) => d.requests));

  const chartHeight = 180;
  const chartWidth = 700;
  const paddingLeft = 40;
  const paddingRight = 16;
  const paddingTop = 16;
  const paddingBottom = 32;
  const plotWidth = chartWidth - paddingLeft - paddingRight;
  const plotHeight = chartHeight - paddingTop - paddingBottom;
  const barGap = 8;
  const groupWidth = plotWidth / data.length;
  const barWidth = (groupWidth - barGap) / 2;

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        className="w-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const y = paddingTop + plotHeight * (1 - frac);
          return (
            <g key={frac}>
              <line
                x1={paddingLeft}
                y1={y}
                x2={chartWidth - paddingRight}
                y2={y}
                stroke="currentColor"
                strokeDasharray="3 3"
                className="text-border"
              />
              <text
                x={paddingLeft - 8}
                y={y}
                textAnchor="end"
                dominantBaseline="middle"
                className="fill-text-muted text-[10px]"
              >
                {frac === 0
                  ? '0'
                  : `${Math.round((maxTokens * frac) / 1000)}k`}
              </text>
            </g>
          );
        })}

        {/* Bars */}
        {data.map((d, i) => {
          const x = paddingLeft + i * groupWidth + barGap / 2;
          const tokensH = (d.tokens / maxTokens) * plotHeight;
          const requestsH = (d.requests / maxRequests) * plotHeight;
          const barY = paddingTop + plotHeight;

          const date = new Date(d.date);
          const label = `${date.getMonth() + 1}/${date.getDate()}`;

          return (
            <g key={d.date}>
              {/* Tokens bar */}
              <rect
                x={x}
                y={barY - tokensH}
                width={barWidth}
                height={tokensH}
                rx={2}
                className="fill-primary transition-opacity hover:opacity-80"
              >
                <title>
                  {formatNumber(d.tokens)} tokens
                </title>
              </rect>
              {/* Requests bar */}
              <rect
                x={x + barWidth}
                y={barY - requestsH}
                width={barWidth}
                height={requestsH}
                rx={2}
                className="fill-accent transition-opacity hover:opacity-80"
              >
                <title>
                  {formatNumber(d.requests)} requests
                </title>
              </rect>
              {/* X-axis label */}
              <text
                x={x + groupWidth / 2 - barGap / 2}
                y={chartHeight - paddingBottom + 18}
                textAnchor="middle"
                className="fill-text-muted text-[10px]"
              >
                {label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default Dashboard;