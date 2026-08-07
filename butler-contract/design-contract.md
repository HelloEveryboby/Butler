# Design Contract — Butler Prototype

## Tech stack + delivery type
stack: **React 19 + Vite + TypeScript + Tailwind CSS v3** (build-type)
delivery: **build** — `npm run build` → static `dist/`
icon lib: **lucide-react** (tree-shaken by bundler)

## Style Tier & Aesthetic Direction
style: **tech-dark**
aesthetic: industrial-utilitarian — command-line precision meets a polished AI control plane. Think Linear × Vercel × a terminal emulator. Grid backgrounds, sharp borders, restrained glow.
tone keywords: calm / dense / professional / trustworthy / high-signal

## Design Tokens

### Colors
| Token | Hex | Usage |
|---|---|---|
| `color.bg` | `#0a0a0b` | App background |
| `color.surface` | `#111113` | Cards, panels |
| `color.surface-2` | `#16161a` | Elevated surfaces, hover |
| `color.border` | `#1f1f23` | Borders, dividers |
| `color.border-strong` | `#2a2a30` | Selected states, focus rings |
| `color.text` | `#e4e4e7` | Primary text |
| `color.text-sub` | `#a1a1aa` | Secondary text, labels |
| `color.text-muted` | `#71717a` | Tertiary text, timestamps |
| `color.primary` | `#10b981` | Emerald — primary accent, success, connected |
| `color.primary-hover` | `#059669` | |
| `color.accent` | `#818cf8` | Indigo — highlights, selection, code |
| `color.warning` | `#f59e0b` | Amber |
| `color.danger` | `#ef4444` | Red — errors, disconnected |
| `color.info` | `#38bdf8` | Sky — tips, help |

### Typography
- `font.display`: **Inter Tight** (headings, compact UI)
- `font.body`: **Inter** (body, text)
- `font.mono`: **JetBrains Mono** (code, logs, timestamps)
- Scale: 12 / 13 / 14 / 16 / 18 / 20 / 24 / 32px
- Default size: 14px body

### Radius & Shadows
- `radius.sm`: 4px | `radius.md`: 8px | `radius.lg`: 12px
- `shadow.sm`: 0 1px 2px rgba(0,0,0,0.4)
- `shadow.md`: 0 4px 12px rgba(0,0,0,0.5)
- `shadow.lg`: 0 12px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)

### Spacing
Base unit: 4px. Scale: 4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64

### Layout
- Sidebar width: 248px (collapsed: 64px)
- Top bar height: 56px
- Content max-width: 1440px
- Grid: 12-column in content area

### Icons
Library: **lucide-react**
Sizes: 16 / 18 / 20 / 24px
Stroke: 1.75px (default), 2px (active)

### Motion
- Page-load: staggered fade-up via CSS `animation` with delays (0ms / 60ms / 120ms / 180ms)
- Hover: 150ms ease-out
- Transition: 200ms ease-out for layout changes
- Skeleton shimmer: 1.4s linear infinite

### Background texture
- Subtle dot-grid pattern at 24px spacing, opacity 0.04 — gives texture without noise
- Accent gradient line (1px) at top of sidebar + top bar — `linear-gradient(90deg, #10b981 0%, #818cf8 100%)`

## Component Spec

### Button
Variants: primary / secondary / ghost / danger / icon
Sizes: sm (h-8) / md (h-9) / lg (h-10)
States: default / hover / active / disabled / loading
- primary: emerald bg `#10b981`, dark text, hover `#059669`
- secondary: surface-2 bg, border, hover surface
- ghost: transparent, hover surface-2
- danger: red bg `#ef4444`
- All buttons use `radius.sm`, 14px font, 500 weight

### Input
- h-9, radius.sm, border `#2a2a30` → focus `#10b981` ring
- Placeholder: `#52525b`
- Font: 14px body, mono variant for code input

### Card
- bg surface, border `#1f1f23`, radius.md
- Padding: 24px default
- Hover: border `#2a2a30`, subtle shadow.md
- Section headers: 16px semibold, text, 12px text-sub label above

### Table
- Header: bg surface-2, text-sub, 12px uppercase tracking-wide
- Row: border-bottom `#1f1f23`, hover surface-2
- Monospace columns (ID, timestamp): JetBrains Mono
- Status tags with dot indicator

### Modal / Drawer
- Backdrop: rgba(0,0,0,0.6), blur 8px
- Panel: surface, border, radius.lg, shadow.lg
- Open animation: scale(0.98) → scale(1), 200ms

### Tag / Badge
- 20px height, radius.sm, 12px font, dot indicator 6px
- Color-coded by type (success/info/warning/danger/neutral)

### Sidebar Nav Item
- h-9, radius.sm, 8px px
- Default: transparent, text-sub
- Hover: surface-2, text
- Active: `rgba(16,185,129,0.12)` bg, emerald dot (4px, 4px left inset), emerald text

### Empty State
- Centered, icon 48px text-muted
- Title 16px semibold text, description 14px text-sub
- Action button below

## App Shell + Canonical Nav

### Shell (React Layout component)
```
<Layout>
  <Sidebar />        // fixed 248px
  <TopBar />         // sticky 56px
  <main>             // content area, ml-62 (margin-left for sidebar)
    <Outlet />
  </main>
</Layout>
```

### Nav items (frozen — Layout renders them)
| Label | Icon (lucide) | Route | Data-nav key |
|---|---|---|---|
| Dashboard | `layout-dashboard` | `/` | dashboard |
| Clients | `server` | `/clients` | clients |
| Playground | `terminal-square` | `/playground` | playground |
| Tools | `wrench` | `/tools` | tools |
| Usage | `bar-chart-3` | `/usage` | usage |
| Logs | `scroll-text` | `/logs` | logs |
| Settings | `settings` | `/settings` | settings |

### Active rule
- Uses `NavLink` with `isActive` checking route path; active item gets emerald bg + left dot + emerald text

### Top bar
- Left: breadcrumb (page title)
- Right: search input (cmd+k), theme toggle, user avatar
- Accent gradient line at bottom

## Page List

| Page | Route | Responsibility | Key components | Navigates to |
|---|---|---|---|---|
| Dashboard | `/` | System overview: active clients, usage stats, recent activity, health status | StatCard, ClientList, ActivityFeed, UsageChart, HealthStatus | → client detail, → playground |
| Clients | `/clients` | Manage registered LLM clients (models, providers, configs); CRUD operations | DataTable, ClientCard, StatusBadge, EmptyState | → client edit modal |
| Playground | `/playground` | Interactive prompt testing; chat with any client/model; compare responses | ChatPanel, ModelSelector, PromptInput, ResponseCompare, UsageBar | → clients |
| Tools | `/tools` | Browse and configure tools/functions available to agents | ToolCard, ToolConfigDrawer, CategoryFilter | → tool detail |
| Usage | `/usage` | Token usage, cost, latency trends; filtering by client/model/time | AreaChart, BarChart, FilterBar, MetricCard, DataTable | → logs |
| Logs | `/logs` | Real-time request log with streaming, filtering, full trace view | LogStream, FilterBar, LogDetailDrawer, StatusPill | → log detail |
| Settings | `/settings` | API keys, environment, theme, integrations, about | SettingsSection, KeyInput, Toggle, Select | — |

## Mock Schema

### Client
```ts
interface Client {
  id: string;           // e.g. "claude-sonnet-4"
  name: string;         // display name
  provider: 'anthropic' | 'openai' | 'google' | 'mistral' | 'custom';
  model: string;
  status: 'connected' | 'disconnected' | 'error';
  config: {
    temperature: number;
    maxTokens: number;
    topP: number;
    systemPrompt: string;
  };
  usage: {
    tokensToday: number;
    requestsToday: number;
    costMonth: number;
  };
  createdAt: string;
  lastActive: string;
}
```

### Tool
```ts
interface Tool {
  id: string;
  name: string;
  description: string;
  category: 'search' | 'code' | 'data' | 'file' | 'web' | 'custom';
  status: 'enabled' | 'disabled';
  configured: boolean;
  usageCount: number;
}
```

### LogEntry
```ts
interface LogEntry {
  id: string;
  timestamp: string;      // ISO
  level: 'info' | 'warn' | 'error' | 'debug';
  clientId: string;
  message: string;
  duration: number;       // ms
  tokens: { input: number; output: number };
  cost: number;           // USD
}
```

### UsagePoint
```ts
interface UsagePoint {
  date: string;       // YYYY-MM-DD
  tokens: number;
  cost: number;
  requests: number;
  byClient: Record<string, { tokens: number; cost: number }>;
}
```

### ActivityItem
```ts
interface ActivityItem {
  id: string;
  type: 'request' | 'config-change' | 'error' | 'tool-call';
  message: string;
  clientId: string;
  timestamp: string;
}
```

### Mock data rules
- 12 clients across 5 providers
- 15 tools across 6 categories
- 50 log entries spanning last 24h
- 30 days of usage data
- 20 activity items for the feed
- All timestamps relative to "now"
- Realistic model IDs, realistic cost per request

## API Stub Conventions
All async service functions in `src/api/` follow real API shapes, annotated with `// TODO: replace with fetch(...)`:
- `getClients()` → `GET /api/clients`
- `createClient(input)` → `POST /api/clients`
- `updateClient(id, input)` → `PATCH /api/clients/:id`
- `deleteClient(id)` → `DELETE /api/clients/:id`
- `getTools()` → `GET /api/tools`
- `getLogs(filters)` → `GET /api/logs`
- `getUsage(range)` → `GET /api/usage`
- `sendPrompt(clientId, messages)` → `POST /api/playground/:clientId/prompt`
- All stubs include `delay(300-800ms)` for realistic loading states
- AI prompt responses are canned but scenario-relevant
