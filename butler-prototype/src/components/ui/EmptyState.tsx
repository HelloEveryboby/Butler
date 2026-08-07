import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-surface-2 text-text-muted">
        {icon}
      </div>
      <h3 className="mb-1.5 font-display text-base font-medium text-text">{title}</h3>
      <p className="mb-5 max-w-sm text-sm text-text-muted">{description}</p>
      {action}
    </div>
  );
}