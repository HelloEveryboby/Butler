import { TrendingUp, TrendingDown } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: string | number;
  change?: number;
  icon?: React.ReactNode;
}

export function StatCard({ label, value, change, icon }: StatCardProps) {
  const isPositive = change !== undefined && change >= 0;
  const isNegative = change !== undefined && change < 0;

  return (
    <div className="rounded-lg border border-border bg-surface p-5 transition-colors hover:border-border-strong">
      <div className="flex items-start justify-between">
        <div className="text-xs font-medium uppercase tracking-wide text-text-muted">{label}</div>
        {icon && <div className="text-text-muted">{icon}</div>}
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="font-display text-2xl font-semibold tracking-tight text-text">{value}</span>
        {change !== undefined && (
          <span
            className={`inline-flex items-center gap-0.5 text-xs font-medium ${
              isPositive ? 'text-primary' : isNegative ? 'text-danger' : 'text-text-muted'
            }`}
          >
            {isPositive && <TrendingUp className="h-3 w-3" />}
            {isNegative && <TrendingDown className="h-3 w-3" />}
            {Math.abs(change).toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}