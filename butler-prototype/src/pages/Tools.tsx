import { useEffect, useState } from 'react';
import {
  Search,
  Code2,
  Database,
  FileCode2,
  Globe,
  Puzzle,
  Settings2,
  Power,
  Plus,
  X,
  Check,
} from 'lucide-react';
import { Card, Badge, Button, EmptyState, Skeleton, Input } from '@/components/ui';
import { getTools, toggleTool } from '@/api';
import type { Tool } from '@/types';

const categories = ['all', 'search', 'code', 'data', 'file', 'web', 'custom'] as const;
type Category = (typeof categories)[number];

const categoryIcons: Record<Tool['category'], typeof Search> = {
  search: Search,
  code: Code2,
  data: Database,
  file: FileCode2,
  web: Globe,
  custom: Puzzle,
};

const categoryLabels: Record<Category, string> = {
  all: 'All',
  search: 'Search',
  code: 'Code',
  data: 'Data',
  file: 'File',
  web: 'Web',
  custom: 'Custom',
};

interface ToolCardProps {
  tool: Tool;
  onToggle: (id: string, status: 'enabled' | 'disabled') => void;
  onConfigure: (tool: Tool) => void;
  toggling: boolean;
}

function ToolCard({ tool, onToggle, onConfigure, toggling }: ToolCardProps) {
  const Icon = categoryIcons[tool.category];
  const isEnabled = tool.status === 'enabled';

  return (
    <Card className="group flex flex-col gap-4 p-5 transition-all hover:border-border-strong hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-lg ${
              isEnabled ? 'bg-primary/15 text-primary' : 'bg-surface-2 text-text-muted'
            }`}
          >
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-display text-sm font-semibold text-text">{tool.name}</h3>
            <Badge variant={isEnabled ? 'success' : 'neutral'} dot>
              {tool.status}
            </Badge>
          </div>
        </div>
      </div>

      <p className="line-clamp-2 text-[13px] leading-relaxed text-text-sub">{tool.description}</p>

      <div className="flex items-center justify-between">
        <Badge variant="neutral">{categoryLabels[tool.category]}</Badge>
        <span className="font-mono text-xs text-text-muted">
          {tool.usageCount.toLocaleString()} uses
        </span>
      </div>

      <div className="mt-auto flex items-center justify-between border-t border-border pt-4">
        <button
          onClick={() => onToggle(tool.id, isEnabled ? 'disabled' : 'enabled')}
          disabled={toggling}
          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
            isEnabled
              ? 'bg-surface-2 text-text-sub hover:bg-danger/15 hover:text-danger'
              : 'bg-surface-2 text-text-sub hover:bg-primary/15 hover:text-primary'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <Power className="h-3 w-3" />
          {isEnabled ? 'Disable' : 'Enable'}
        </button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onConfigure(tool)}
          className="gap-1.5"
        >
          <Settings2 className="h-3.5 w-3.5" />
          Configure
        </Button>
      </div>
    </Card>
  );
}

interface ToolConfigDrawerProps {
  tool: Tool | null;
  onClose: () => void;
  onSave: (id: string, status: 'enabled' | 'disabled') => void;
}

function ToolConfigDrawer({ tool, onClose, onSave }: ToolConfigDrawerProps) {
  const [localStatus, setLocalStatus] = useState<'enabled' | 'disabled'>(
    tool?.status ?? 'disabled',
  );
  const [apiKey, setApiKey] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [defaultParams, setDefaultParams] = useState('');

  useEffect(() => {
    if (tool) {
      setLocalStatus(tool.status);
      setApiKey('');
      setEndpoint('');
      setDefaultParams('');
    }
  }, [tool]);

  if (!tool) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-bg/60 backdrop-blur-sm" onClick={onClose} />
      <div className="animate-fade-up absolute right-0 top-0 flex h-full w-full max-w-md flex-col border-l border-border bg-surface shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div className="flex items-center gap-3">
            <div
              className={`flex h-9 w-9 items-center justify-center rounded-lg ${
                localStatus === 'enabled' ? 'bg-primary/15 text-primary' : 'bg-surface-2 text-text-muted'
              }`}
            >
              {(() => {
                const Icon = categoryIcons[tool.category];
                return <Icon className="h-5 w-5" />;
              })()}
            </div>
            <div>
              <h3 className="font-display text-base font-semibold text-text">{tool.name}</h3>
              <Badge variant={localStatus === 'enabled' ? 'success' : 'neutral'} dot>
                {localStatus}
              </Badge>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-text-sub">Description</label>
            <p className="text-[13px] leading-relaxed text-text">{tool.description}</p>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border bg-surface-2 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-text">Status</p>
              <p className="text-xs text-text-muted">
                {localStatus === 'enabled' ? 'Tool is active and available' : 'Tool is disabled'}
              </p>
            </div>
            <button
              onClick={() => setLocalStatus(localStatus === 'enabled' ? 'disabled' : 'enabled')}
              className={`relative h-5 w-9 rounded-full transition-colors ${
                localStatus === 'enabled' ? 'bg-primary' : 'bg-surface'
              }`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-text shadow transition-transform ${
                  localStatus === 'enabled' ? 'translate-x-4' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>

          <Input
            label="API Key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Enter API key..."
          />

          <Input
            label="Endpoint URL"
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            placeholder="https://api.example.com"
          />

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-text-sub">Default Parameters (JSON)</label>
            <textarea
              value={defaultParams}
              onChange={(e) => setDefaultParams(e.target.value)}
              placeholder='{"timeout": 30, "retry": 2}'
              className="h-24 w-full resize-none rounded-md border border-border bg-surface-2 px-3 py-2 text-[13px] font-mono text-text placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
            />
          </div>

          <div className="rounded-lg border border-border bg-surface-2 p-4">
            <p className="mb-2 text-xs font-medium text-text-sub">Usage Statistics</p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="font-mono text-lg text-text">{tool.usageCount.toLocaleString()}</p>
                <p className="text-xs text-text-muted">Total uses</p>
              </div>
              <div>
                <p className="font-mono text-lg text-text">{tool.configured ? 'Yes' : 'No'}</p>
                <p className="text-xs text-text-muted">Configured</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-border px-5 py-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={() => onSave(tool.id, localStatus)} className="gap-2">
            <Check className="h-3.5 w-3.5" />
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  );
}

function ToolSkeleton() {
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Skeleton variant="circular" className="h-10 w-10 rounded-lg" />
          <div className="space-y-2">
            <Skeleton variant="text" className="h-4 w-24" />
            <Skeleton variant="text" className="h-3 w-16" />
          </div>
        </div>
      </div>
      <Skeleton variant="text" className="h-4 w-full" />
      <Skeleton variant="text" className="h-4 w-3/4" />
      <div className="flex items-center justify-between pt-2">
        <Skeleton variant="text" className="h-4 w-20" />
        <Skeleton variant="text" className="h-4 w-16" />
      </div>
      <div className="flex items-center justify-between border-t border-border pt-4">
        <Skeleton variant="text" className="h-6 w-20" />
        <Skeleton variant="text" className="h-6 w-24" />
      </div>
    </Card>
  );
}

export default function Tools() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState<Category>('all');
  const [configuringTool, setConfiguringTool] = useState<Tool | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  useEffect(() => {
    getTools()
      .then((data) => setTools(data))
      .finally(() => setLoading(false));
  }, []);

  const filteredTools =
    activeCategory === 'all'
      ? tools
      : tools.filter((t) => t.category === activeCategory);

  const handleToggle = async (id: string, status: 'enabled' | 'disabled') => {
    setTogglingId(id);
    try {
      const updated = await toggleTool(id, status);
      setTools((prev) => prev.map((t) => (t.id === id ? updated : t)));
    } finally {
      setTogglingId(null);
    }
  };

  const handleSaveConfig = (id: string, status: 'enabled' | 'disabled') => {
    setTools((prev) => prev.map((t) => (t.id === id ? { ...t, status } : t)));
    setConfiguringTool(null);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <div className="animate-fade-up flex items-center justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-text">Tools</h1>
          <p className="mt-1 text-sm text-text-muted">Extend Butler with tools and function plugins</p>
        </div>
        <Button variant="primary" className="gap-2">
          <Plus className="h-4 w-4" />
          Add Tool
        </Button>
      </div>

      <div
        className="animate-fade-up flex flex-wrap items-center gap-2"
        style={{ animationDelay: '60ms' }}
      >
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors ${
              activeCategory === cat
                ? 'bg-primary text-bg'
                : 'bg-surface-2 text-text-sub hover:bg-border hover:text-text'
            }`}
          >
            {categoryLabels[cat]}
            {cat !== 'all' && (
              <span className="ml-1.5 opacity-60">
                {tools.filter((t) => t.category === cat).length}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="animate-fade-up" style={{ animationDelay: '120ms' }}>
        {loading ? (
          <div className="grid grid-cols-3 gap-4">
            {Array.from({ length: 9 }).map((_, i) => (
              <div key={i} style={{ animationDelay: `${i * 60}ms` }}>
                <ToolSkeleton />
              </div>
            ))}
          </div>
        ) : filteredTools.length === 0 ? (
          <Card>
            <EmptyState
              icon={<Search className="h-6 w-6" />}
              title="No tools found"
              description={`No tools found in the ${categoryLabels[activeCategory]} category. Try selecting a different category or add a new tool.`}
              action={
                activeCategory !== 'all' ? (
                  <Button variant="secondary" size="sm" onClick={() => setActiveCategory('all')}>
                    View all tools
                  </Button>
                ) : (
                  <Button variant="primary" size="sm" className="gap-1.5">
                    <Plus className="h-3.5 w-3.5" />
                    Add your first tool
                  </Button>
                )
              }
            />
          </Card>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {filteredTools.map((tool, idx) => (
              <div
                key={tool.id}
                className="animate-fade-up"
                style={{ animationDelay: `${idx * 60}ms` }}
              >
                <ToolCard
                  tool={tool}
                  onToggle={handleToggle}
                  onConfigure={setConfiguringTool}
                  toggling={togglingId === tool.id}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      <ToolConfigDrawer
        tool={configuringTool}
        onClose={() => setConfiguringTool(null)}
        onSave={handleSaveConfig}
      />
    </div>
  );
}