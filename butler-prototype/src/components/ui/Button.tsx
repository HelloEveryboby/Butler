import { forwardRef, type ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'icon';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-primary text-bg hover:bg-primary-hover shadow-sm disabled:bg-primary/40 disabled:cursor-not-allowed',
  secondary:
    'bg-surface-2 text-text border border-border hover:border-border-strong hover:bg-border disabled:opacity-50 disabled:cursor-not-allowed',
  ghost:
    'bg-transparent text-text-sub hover:bg-surface-2 hover:text-text disabled:opacity-50 disabled:cursor-not-allowed',
  danger:
    'bg-danger text-white hover:bg-red-600 shadow-sm disabled:bg-danger/40 disabled:cursor-not-allowed',
  icon:
    'bg-transparent text-text-sub hover:bg-surface-2 hover:text-text disabled:opacity-50 disabled:cursor-not-allowed',
};

const sizeClasses: Record<Size, string> = {
  sm: 'h-7 px-3 text-xs gap-1.5',
  md: 'h-9 px-4 text-[13px] gap-2',
  lg: 'h-11 px-6 text-sm gap-2',
};

const iconSizeClasses: Record<Size, string> = {
  sm: 'h-7 w-7 p-0',
  md: 'h-9 w-9 p-0',
  lg: 'h-11 w-11 p-0',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading = false, className = '', children, disabled, ...props },
  ref,
) {
  const isIconOnly = variant === 'icon';
  const classes = [
    'inline-flex items-center justify-center rounded-md font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-2 focus:ring-offset-bg',
    isIconOnly ? iconSizeClasses[size] : sizeClasses[size],
    variantClasses[variant],
    loading ? 'opacity-70 cursor-wait' : '',
    className,
  ].join(' ');

  return (
    <button ref={ref} className={classes} disabled={disabled || loading} {...props}>
      {loading && (
        <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  );
});