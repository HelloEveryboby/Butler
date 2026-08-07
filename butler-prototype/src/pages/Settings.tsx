import { useState, useEffect, type ComponentType, type SVGProps } from 'react';
import {
  Settings as SettingsIcon,
  Key,
  Server,
  Plug,
  Info,
  ChevronRight,
  X,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  RotateCw,
  Trash,
  Copy,
  Check,
  ExternalLink,
  BookOpen,
  MessageSquare,
  Zap,
  Shield,
  Cpu,
  HardDrive,
  FolderOpen,
  Code,
} from 'lucide-react';
import { Card, CardBody } from '@/components/ui/Card.js';
import { Button } from '@/components/ui/Button.js';
import { Badge } from '@/components/ui/Badge.js';
import { Input } from '@/components/ui/Input.js';
import { Select } from '@/components/ui/Select.js';
import { Skeleton } from '@/components/ui/Skeleton.js';

type TabId = 'general' | 'keys' | 'environment' | 'integrations' | 'about';

const tabs: { id: TabId; label: string; icon: ComponentType<SVGProps<SVGSVGElement>> }[] = [
  { id: 'general', label: 'General', icon: SettingsIcon },
  { id: 'keys', label: 'API Keys', icon: Key },
  { id: 'environment', label: 'Environment', icon: Server },
  { id: 'integrations', label: 'Integrations', icon: Plug },
  { id: 'about', label: 'About', icon: Info },
];

interface ApiKey {
  id: string;
  name: string;
  provider: string;
  last4: string;
  tokens: number;
  requests: number;
  cost: number;
  createdAt: string;
}

const mockApiKeys: ApiKey[] = [
  { id: 'k1', name: 'Production Primary', provider: 'anthropic', last4: '4a2f', tokens: 2845321, requests: 12847, cost: 847.23, createdAt: '2024-01-15' },
  { id: 'k2', name: 'Analytics Pipeline', provider: 'openai', last4: '9b1c', tokens: 1423910, requests: 5621, cost: 423.50, createdAt: '2024-02-20' },
  { id: 'k3', name: 'Backup Key', provider: 'google', last4: '7d8e', tokens: 124532, requests: 892, cost: 34.12, createdAt: '2024-03-10' },
];

interface Integration {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  lastSync: string | null;
  url: string;
}

const mockIntegrations: Integration[] = [
  { id: 'slack', name: 'Slack', description: 'Send notifications to Slack channels and respond to mentions', enabled: true, lastSync: '2 min ago', url: 'slack.com' },
  { id: 'discord', name: 'Discord', description: 'Bridge Butler into Discord servers for interactive sessions', enabled: false, lastSync: null, url: 'discord.com' },
  { id: 'github', name: 'GitHub', description: 'Link issues, PRs, and commits to request traces', enabled: true, lastSync: '1 hr ago', url: 'github.com' },
  { id: 'notion', name: 'Notion', description: 'Export results and logs to Notion databases', enabled: false, lastSync: null, url: 'notion.so' },
];

function formatCost(n: number): string {
  return n >= 1000 ? `$${(n / 1000).toFixed(1)}K` : `$${n.toFixed(2)}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toString();
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState<TabId>('general');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 400);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-6">
      <div className="animate-fade-up">
        <h1 className="font-display text-xl font-semibold tracking-tight text-text">Settings</h1>
        <p className="mt-1 text-sm text-text-muted">Configure your Butler environment</p>
      </div>

      <div className="animate-fade-up animation-delay-60 flex gap-6">
        <nav className="w-[180px] flex-shrink-0">
          <div className="sticky top-6 space-y-0.5">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`group flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-colors ${
                    isActive
                      ? 'bg-[rgba(16,185,129,0.12)] text-primary'
                      : 'text-text-sub hover:bg-surface-2 hover:text-text'
                  }`}
                >
                  <Icon className="h-4 w-4 flex-shrink-0" strokeWidth={2} />
                  <span>{tab.label}</span>
                  {isActive && (
                    <ChevronRight className="ml-auto h-3.5 w-3.5 text-primary" />
                  )}
                </button>
              );
            })}
          </div>
        </nav>

        <div className="min-w-0 flex-1">
          {loading ? (
            <Card>
              <CardBody>
                <Skeleton variant="text" className="w-1/3" />
                <Skeleton variant="rectangular" className="mt-4 h-40" />
                <Skeleton variant="text" className="mt-4 w-1/2" />
                <Skeleton variant="text" className="mt-2 w-2/3" />
              </CardBody>
            </Card>
          ) : (
            <>
              {activeTab === 'general' && <GeneralTab />}
              {activeTab === 'keys' && <ApiKeysTab />}
              {activeTab === 'environment' && <EnvironmentTab />}
              {activeTab === 'integrations' && <IntegrationsTab />}
              {activeTab === 'about' && <AboutTab />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function GeneralTab() {
  const [workspaceName, setWorkspaceName] = useState('Butler Production');
  const [timezone, setTimezone] = useState('UTC');
  const [language, setLanguage] = useState('English');
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [autoSave, setAutoSave] = useState(true);
  const [defaultClient, setDefaultClient] = useState('c1');

  return (
    <Card className="animate-fade-up">
      <CardBody className="space-y-6">
        <h2 className="font-display text-base font-semibold text-text">General Settings</h2>

        <div className="space-y-4">
          <Input
            label="Workspace Name"
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
          />

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Timezone"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              <option>UTC</option>
              <option>America/New_York</option>
              <option>America/Los_Angeles</option>
              <option>Europe/London</option>
              <option>Europe/Berlin</option>
              <option>Asia/Tokyo</option>
              <option>Asia/Shanghai</option>
            </Select>

            <Select
              label="Default Language"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option>English</option>
              <option>Spanish</option>
              <option>French</option>
              <option>German</option>
              <option>Japanese</option>
              <option>Chinese</option>
            </Select>
          </div>
        </div>

        <div className="border-t border-border pt-5">
          <span className="mb-3 block text-xs font-medium text-text-sub">Theme</span>
          <div className="flex gap-3">
            <button
              onClick={() => setTheme('dark')}
              className={`flex flex-1 flex-col items-center gap-2 rounded-lg border p-3 transition-colors ${
                theme === 'dark'
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:border-border-strong'
              }`}
            >
              <div className="h-12 w-full rounded-md bg-gradient-to-br from-zinc-900 to-zinc-800" />
              <span className="text-xs font-medium text-text">Dark</span>
              {theme === 'dark' && (
                <Check className="h-3.5 w-3.5 text-primary" />
              )}
            </button>
            <button
              disabled
              className="flex flex-1 flex-col items-center gap-2 rounded-lg border border-border p-3 opacity-50"
            >
              <div className="h-12 w-full rounded-md bg-gradient-to-br from-zinc-100 to-zinc-200" />
              <span className="text-xs font-medium text-text-muted">Light</span>
              <span className="text-[10px] text-text-muted">Coming soon</span>
            </button>
          </div>
        </div>

        <div className="border-t border-border pt-5">
          <h3 className="mb-3 text-sm font-medium text-text">Preferences</h3>
          <div className="space-y-3">
            <label className="flex cursor-pointer items-center justify-between rounded-md border border-border bg-surface-2 px-4 py-3">
              <div>
                <div className="text-sm text-text">Auto-save changes</div>
                <div className="text-xs text-text-muted">
                  Automatically save configuration changes as you make them
                </div>
              </div>
              <Toggle checked={autoSave} onChange={setAutoSave} />
            </label>

            <div className="rounded-md border border-border bg-surface-2 px-4 py-3">
              <div className="mb-2 text-sm text-text">Default Client</div>
              <div className="text-xs text-text-muted mb-2">
                Client pre-selected for new requests
              </div>
              <Select
                value={defaultClient}
                onChange={(e) => setDefaultClient(e.target.value)}
                className="h-8"
              >
                <option value="c1">Production API</option>
                <option value="c2">Analytics Pipeline</option>
                <option value="c3">Customer Support Bot</option>
                <option value="c4">Code Review Assistant</option>
              </Select>
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative h-5 w-9 flex-shrink-0 rounded-full transition-colors ${
        checked ? 'bg-primary' : 'bg-border'
      }`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${
          checked ? 'left-[18px]' : 'left-0.5'
        }`}
      />
    </button>
  );
}

function ApiKeysTab() {
  const [keys, setKeys] = useState<ApiKey[]>(mockApiKeys);
  const [showAddModal, setShowAddModal] = useState(false);
  const [visibleIds, setVisibleIds] = useState<Set<string>>(new Set());
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyProvider, setNewKeyProvider] = useState('anthropic');
  const [newKeyValue, setNewKeyValue] = useState('');

  const toggleVisibility = (id: string) => {
    setVisibleIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAddKey = () => {
    if (!newKeyName || !newKeyValue) return;
    const last4 = newKeyValue.slice(-4);
    const newKey: ApiKey = {
      id: `k${Date.now()}`,
      name: newKeyName,
      provider: newKeyProvider,
      last4,
      tokens: 0,
      requests: 0,
      cost: 0,
      createdAt: new Date().toISOString().slice(0, 10),
    };
    setKeys((prev) => [newKey, ...prev]);
    setShowAddModal(false);
    setNewKeyName('');
    setNewKeyValue('');
    setNewKeyProvider('anthropic');
  };

  const handleDelete = (id: string) => {
    setKeys((prev) => prev.filter((k) => k.id !== id));
  };

  const handleRotate = (id: string) => {
    setKeys((prev) =>
      prev.map((k) =>
        k.id === id
          ? { ...k, last4: Math.random().toString(16).slice(2, 6) }
          : k,
      ),
    );
  };

  return (
    <Card className="animate-fade-up">
      <CardBody className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-base font-semibold text-text">API Keys</h2>
          <Button size="sm" onClick={() => setShowAddModal(true)}>
            <Plus className="h-3.5 w-3.5" />
            Add Key
          </Button>
        </div>

        <div className="space-y-2">
          {keys.map((key) => (
            <div
              key={key.id}
              className="rounded-lg border border-border bg-surface-2 p-4"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10">
                    <Key className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-text">{key.name}</div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-text-muted">
                      <span>{key.provider}</span>
                      <span>•</span>
                      <span>Created {key.createdAt}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => toggleVisibility(key.id)}
                    className="flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-surface hover:text-text"
                    title={visibleIds.has(key.id) ? 'Hide key' : 'Show key'}
                  >
                    {visibleIds.has(key.id) ? (
                      <Eye className="h-3.5 w-3.5" />
                    ) : (
                      <EyeOff className="h-3.5 w-3.5" />
                    )}
                  </button>
                  <button
                    onClick={() => handleRotate(key.id)}
                    className="flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-surface hover:text-text"
                    title="Regenerate key"
                  >
                    <RotateCw className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => handleDelete(key.id)}
                    className="flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-danger/10 hover:text-danger"
                    title="Delete key"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              <div className="mt-3 flex items-center gap-3 rounded-md border border-border bg-bg px-3 py-2 font-mono text-xs">
                <span className="text-text-muted">
                  {visibleIds.has(key.id)
                    ? `sk-${key.provider}-${key.last4}${Math.random().toString(36).slice(2, 14)}`
                    : `••••••••••••••${key.last4}`}
                </span>
                <button className="ml-auto text-text-muted transition-colors hover:text-text">
                  <Copy className="h-3 w-3" />
                </button>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-4 border-t border-border pt-3">
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-text-muted">Tokens</div>
                  <div className="mt-0.5 font-mono text-sm text-text">
                    {formatTokens(key.tokens)}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-text-muted">Requests</div>
                  <div className="mt-0.5 font-mono text-sm text-text">
                    {key.requests.toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wide text-text-muted">Cost</div>
                  <div className="mt-0.5 font-mono text-sm text-text">
                    {formatCost(key.cost)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardBody>

      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-surface shadow-xl">
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <h3 className="font-display text-base font-semibold text-text">Add API Key</h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="flex h-7 w-7 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-surface-2 hover:text-text"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="space-y-4 p-5">
              <Select
                label="Provider"
                value={newKeyProvider}
                onChange={(e) => setNewKeyProvider(e.target.value)}
              >
                <option value="anthropic">Anthropic</option>
                <option value="openai">OpenAI</option>
                <option value="google">Google</option>
                <option value="mistral">Mistral</option>
                <option value="custom">Custom</option>
              </Select>
              <Input
                label="Key Name"
                placeholder="e.g. Production Backup"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
              />
              <Input
                label="API Key"
                placeholder="sk-..."
                value={newKeyValue}
                onChange={(e) => setNewKeyValue(e.target.value)}
              />
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => setShowAddModal(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddKey} disabled={!newKeyName || !newKeyValue}>
                  Add Key
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

function EnvironmentTab() {
  const [envs, setEnvs] = useState<{ key: string; value: string; visible: boolean }[]>([
    { key: 'BUTLER_HOME', value: '/opt/butler', visible: false },
    { key: 'BUTLER_ENV', value: 'production', visible: false },
    { key: 'BUTLER_LOG_LEVEL', value: 'info', visible: false },
    { key: 'BUTLER_MAX_CONCURRENCY', value: '10', visible: false },
    { key: 'DATABASE_URL', value: 'postgresql://localhost:5432/butler', visible: false },
    { key: 'REDIS_URL', value: 'redis://localhost:6379', visible: false },
  ]);

  const toggleEnv = (idx: number) => {
    setEnvs((prev) =>
      prev.map((e, i) => (i === idx ? { ...e, visible: !e.visible } : e)),
    );
  };

  return (
    <Card className="animate-fade-up">
      <CardBody className="space-y-6">
        <h2 className="font-display text-base font-semibold text-text">Environment</h2>

        <div className="rounded-lg border border-border bg-surface-2 p-4">
          <span className="mb-3 block text-xs font-medium text-text-muted">Runtime Info</span>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex items-center gap-2">
              <Cpu className="h-3.5 w-3.5 text-text-muted" />
              <span className="text-xs text-text-muted">Python:</span>
              <span className="font-mono text-xs text-text">3.12.4</span>
            </div>
            <div className="flex items-center gap-2">
              <Zap className="h-3.5 w-3.5 text-text-muted" />
              <span className="text-xs text-text-muted">Butler:</span>
              <span className="font-mono text-xs text-text">1.0.0</span>
            </div>
            <div className="flex items-center gap-2">
              <HardDrive className="h-3.5 w-3.5 text-text-muted" />
              <span className="text-xs text-text-muted">OS:</span>
              <span className="font-mono text-xs text-text">Linux x86_64</span>
            </div>
            <div className="flex items-center gap-2">
              <FolderOpen className="h-3.5 w-3.5 text-text-muted" />
              <span className="text-xs text-text-muted">Path:</span>
              <span className="font-mono text-xs text-text">/opt/butler</span>
            </div>
          </div>
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-medium text-text-muted">Environment Variables</span>
            <span className="text-[11px] text-text-muted">{envs.length} variables</span>
          </div>
          <div className="overflow-hidden rounded-lg border border-border">
            {envs.map((env, i) => (
              <div
                key={env.key}
                className={`flex items-center gap-3 px-4 py-2 font-mono text-xs ${
                  i > 0 ? 'border-t border-border' : ''
                }`}
              >
                <span className="w-48 flex-shrink-0 text-text-muted">{env.key}</span>
                <span className="flex-1 truncate text-text">
                  {env.visible ? env.value : '••••••••••••'}
                </span>
                <button
                  onClick={() => toggleEnv(i)}
                  className="flex h-5 w-5 items-center justify-center rounded text-text-muted transition-colors hover:text-text"
                >
                  {env.visible ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                </button>
                <button className="flex h-5 w-5 items-center justify-center rounded text-text-muted transition-colors hover:text-text">
                  <Copy className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="flex gap-2 border-t border-border pt-5">
          <Button variant="secondary" size="sm">
            <RotateCw className="h-3.5 w-3.5" />
            Restart Server
          </Button>
          <Button variant="secondary" size="sm">
            <Trash className="h-3.5 w-3.5" />
            Clear Cache
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

function IntegrationsTab() {
  const [integrations, setIntegrations] = useState<Integration[]>(mockIntegrations);

  const toggleIntegration = (id: string) => {
    setIntegrations((prev) =>
      prev.map((i) =>
        i.id === id
          ? { ...i, enabled: !i.enabled, lastSync: !i.enabled ? 'just now' : null }
          : i,
      ),
    );
  };

  return (
    <Card className="animate-fade-up">
      <CardBody className="space-y-4">
        <h2 className="font-display text-base font-semibold text-text">Integrations</h2>
        <p className="text-sm text-text-muted">
          Connect Butler with external services to extend its capabilities.
        </p>

        <div className="space-y-3">
          {integrations.map((integration) => (
            <div
              key={integration.id}
              className="flex items-start gap-4 rounded-lg border border-border bg-surface-2 p-4"
            >
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10">
                {integration.id === 'slack' && (
                  <span className="text-base">#</span>
                )}
                {integration.id === 'discord' && (
                  <span className="text-base">◈</span>
                )}
                {integration.id === 'github' && (
                  <Code className="h-5 w-5 text-primary" />
                )}
                {integration.id === 'notion' && (
                  <span className="font-bold text-sm text-primary">N</span>
                )}
              </div>

              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-text">{integration.name}</span>
                  {integration.enabled ? (
                    <Badge variant="success" dot className="text-[10px]">
                      Connected
                    </Badge>
                  ) : (
                    <Badge variant="neutral" dot className="text-[10px]">
                      Disconnected
                    </Badge>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-text-muted">{integration.description}</p>
                {integration.lastSync && (
                  <p className="mt-1 text-[11px] text-text-muted">
                    Last sync: {integration.lastSync}
                  </p>
                )}
              </div>

              <div className="flex flex-col items-end gap-2">
                <Toggle
                  checked={integration.enabled}
                  onChange={() => toggleIntegration(integration.id)}
                />
                <button className="flex items-center gap-1 text-[11px] text-text-muted transition-colors hover:text-accent">
                  <ExternalLink className="h-3 w-3" />
                  {integration.url}
                </button>
              </div>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

function AboutTab() {
  return (
    <Card className="animate-fade-up">
      <CardBody className="space-y-6">
        <h2 className="font-display text-base font-semibold text-text">About Butler</h2>

        <div className="rounded-lg border border-border bg-surface-2 p-4">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary">
              <span className="font-display text-lg font-bold text-bg">B</span>
            </div>
            <div>
              <div className="font-display text-lg font-semibold text-text">Butler</div>
              <div className="text-xs text-text-muted">LLM Client Manager</div>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-4 border-t border-border pt-4">
            <div>
              <div className="text-[10px] uppercase tracking-wide text-text-muted">Version</div>
              <div className="mt-0.5 font-mono text-sm text-text">1.0.0</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-text-muted">Build</div>
              <div className="mt/0.5 font-mono text-sm text-text">2025-08-07</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wide text-text-muted">License</div>
              <div className="mt/0.5 font-mono text-sm text-text">MIT</div>
            </div>
          </div>
        </div>

        <div>
          <h3 className="mb-3 text-sm font-medium text-text">Links</h3>
          <div className="grid grid-cols-2 gap-2">
            <a
              href="#"
              className="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-4 py-3 text-sm text-text transition-colors hover:border-border-strong"
            >
              <BookOpen className="h-4 w-4 text-text-muted" />
              Documentation
            </a>
            <a
              href="#"
              className="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-4 py-3 text-sm text-text transition-colors hover:border-border-strong"
            >
              <Code className="h-4 w-4 text-text-muted" />
              GitHub
            </a>
            <a
              href="#"
              className="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-4 py-3 text-sm text-text transition-colors hover:border-border-strong"
            >
              <MessageSquare className="h-4 w-4 text-text-muted" />
              Feedback
            </a>
            <a
              href="#"
              className="flex items-center gap-2 rounded-md border border-border bg-surface-2 px-4 py-3 text-sm text-text transition-colors hover:border-border-strong"
            >
              <Shield className="h-4 w-4 text-text-muted" />
              Security
            </a>
          </div>
        </div>

        <div className="border-t border-border pt-5">
          <h3 className="mb-2 text-sm font-medium text-text">Credits</h3>
          <p className="text-xs text-text-muted">
            Built with React, Tailwind CSS, and Vite. Butler is an open-source project
            maintained by the community. Special thanks to all contributors.
          </p>
        </div>

        <div className="border-t border-border pt-5">
          <h3 className="mb-2 text-sm font-medium text-text">Acknowledgments</h3>
          <div className="space-y-2 text-xs text-text-muted">
            <p>
              <span className="text-text">Anthropic</span> — For Claude AI models that power many Butler clients
            </p>
            <p>
              <span className="text-text">OpenAI</span> — For GPT models and API services
            </p>
            <p>
              <span className="text-text">Google</span> — For Gemini models and cloud infrastructure
            </p>
            <p>
              <span className="text-text">The open-source community</span> — For continuous support and contributions
            </p>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

