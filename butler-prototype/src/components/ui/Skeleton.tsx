interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular';
  animationDelay?: number;
}

export function Skeleton({
  className = '',
  variant = 'text',
  animationDelay = 0,
}: SkeletonProps) {
  const variantClasses: Record<string, string> = {
    text: 'h-4 w-full rounded',
    circular: 'h-10 w-10 rounded-full',
    rectangular: 'h-20 w-full rounded-md',
  };

  return (
    <div
      className={`shimmer-bg animate-shimmer ${variantClasses[variant]} ${className}`}
      style={{ animationDelay: `${animationDelay}ms` }}
    />
  );
}

export function SkeletonRow() {
  return (
    <div className="space-y-3">
      <Skeleton variant="text" className="w-1/3" />
      <Skeleton variant="text" />
      <Skeleton variant="text" className="w-2/3" />
      <Skeleton variant="rectangular" />
      <Skeleton variant="text" className="w-1/2" animationDelay={150} />
      <Skeleton variant="text" className="w-3/4" animationDelay={200} />
    </div>
  );
}