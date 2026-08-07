import type { HTMLAttributes } from 'react';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  dot?: boolean;
}

const variantClasses: Record<BadgeVariant, { bg: string; dot: string; text: string }> = {
  success: { bg: 'bg-primary/12', dot: 'bg-primary', text: 'text-primary' },
  warning: { bg: 'bg-warning/12', dot: 'bg-warning', text: 'text-warning' },
  danger: { bg: 'bg-danger/12', dot: 'bg-danger', text: 'text-danger' },
  info: { bg: 'bg-info/12', dot: 'bg-info', text: 'text-info' },
  neutral: { bg: 'bg-surface-2', dot: 'bg-text-muted', text: 'text-text-sub' },
};

export function Badge({ variant = 'neutral', dot = false, className = '', children, ...props }: BadgeProps) {
  const v = variantClasses[variant];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${v.bg} ${v.text} ${className}`}
      {...props}
    >
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${v.dot}`} />}
      {children}
    </span>
  );
}