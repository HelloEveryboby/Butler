import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Server,
  TerminalSquare,
  Wrench,
  BarChart3,
  ScrollText,
  Settings,
  Search,
} from 'lucide-react';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/clients', label: 'Clients', icon: Server },
  { to: '/playground', label: 'Playground', icon: TerminalSquare },
  { to: '/tools', label: 'Tools', icon: Wrench },
  { to: '/usage', label: 'Usage', icon: BarChart3 },
  { to: '/logs', label: 'Logs', icon: ScrollText },
  { to: '/settings', label: 'Settings', icon: Settings },
] as const;

const breadcrumbMap: Record<string, string> = {
  '/': 'Dashboard',
  '/clients': 'Clients',
  '/playground': 'Playground',
  '/tools': 'Tools',
  '/usage': 'Usage',
  '/logs': 'Logs',
  '/settings': 'Settings',
};

export default function Layout() {
  const location = useLocation();
  const breadcrumb = breadcrumbMap[location.pathname] ?? 'Butler';

  return (
    <div className="flex h-screen bg-bg text-text">
      <aside className="flex w-62 flex-shrink-0 flex-col border-r border-border bg-surface">
        <div className="flex h-14 items-center gap-2.5 border-b border-border px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary">
            <span className="font-display text-sm font-bold text-bg">B</span>
          </div>
          <div className="flex flex-col leading-tight">
            <span className="font-display text-[15px] font-semibold tracking-tight text-text">Butler</span>
            <span className="text-[11px] text-text-muted">LLM Client Manager</span>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto py-2">
          <ul className="space-y-0.5 px-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) =>
                      [
                        'group relative flex items-center gap-3 rounded-md px-3 py-2 text-[13px] font-medium transition-colors',
                        isActive
                          ? 'bg-[rgba(16,185,129,0.12)] text-primary'
                          : 'text-text-sub hover:bg-surface-2 hover:text-text',
                      ].join(' ')
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r bg-primary" />
                        )}
                        <Icon className="h-4 w-4 flex-shrink-0" strokeWidth={2} />
                        <span>{item.label}</span>
                      </>
                    )}
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-t border-border p-3">
          <div className="rounded-md border border-border bg-surface-2 p-3">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-primary" />
              <span className="text-xs font-medium text-text">System Online</span>
            </div>
            <p className="mt-1 text-[11px] text-text-muted">All providers operational</p>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-border bg-surface px-6">
          <div className="flex items-center gap-2 text-[13px] text-text-sub">
            <span className="text-text-muted">Butler</span>
            <span className="text-text-muted">/</span>
            <span className="font-medium text-text">{breadcrumb}</span>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
              <input
                type="text"
                placeholder="Search..."
                className="h-8 w-56 rounded-md border border-border bg-surface-2 pl-9 pr-12 text-[13px] text-text placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-border bg-bg px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
                ⌘K
              </kbd>
            </div>

            <div className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface-2">
              <span className="font-display text-xs font-semibold text-text">JD</span>
            </div>
          </div>
        </header>

        <div className="h-[2px] w-full bg-gradient-to-r from-primary/40 via-accent/30 to-transparent" />

        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}