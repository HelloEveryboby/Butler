import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Plus,
  Pencil,
  Trash2,
  Search,
  X,
  Server,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { getClients, createClient, updateClient, deleteClient } from '@/api';
import type { Client, ClientInput } from '@/types';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardBody } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Table } from '@/components/ui/Table';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';

const providerOptions = [
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'google', label: 'Google' },
  { value: 'mistral', label: 'Mistral' },
  { value: 'custom', label: 'Custom' },
] as const;

const modelOptions: Record<string, string[]> = {
  anthropic: ['claude-3.7-sonnet-20250219', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229'],
  openai: ['gpt-4o-2025-08-01', 'gpt-4o-mini-2024-07-18', 'gpt-4.1-2025-03-01', 'o3-mini-2025-01-31'],
  google: ['gemini-2.5-pro', 'gemini-2.0-flash'],
  mistral: ['mistral-large-2.0', 'mistral-nemo-12b'],
  custom: ['custom-math-70b'],
};

interface ClientFormState {
  name: string;
  provider: Client['provider'];
  model: string;
  temperature: number;
  maxTokens: number;
  topP: number;
  systemPrompt: string;
}

const defaultFormState: ClientFormState = {
  name: '',
  provider: 'anthropic',
  model: 'claude-3.7-sonnet-20250219',
  temperature: 0.7,
  maxTokens: 4096,
  topP: 0.9,
  systemPrompt: '',
};

function formatCurrency(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatNumber(n: number): string {
  return n.toLocaleString();
}

function formatLastActive(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function Clients() {
  const [clients, setClients] = useState<Client[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [providerFilter, setProviderFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<Client | null>(null);
  const [form, setForm] = useState<ClientFormState>(defaultFormState);
  const [formErrors, setFormErrors] = useState<Partial<Record<keyof ClientFormState, string>>>({});
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<Client | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const loadClients = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getClients();
      setClients(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadClients();
  }, [loadClients]);

  const filteredClients = useMemo(() => {
    if (!clients) return [];
    return clients.filter((c) => {
      if (search && !c.name.toLowerCase().includes(search.toLowerCase()) && !c.model.toLowerCase().includes(search.toLowerCase())) {
        return false;
      }
      if (providerFilter && c.provider !== providerFilter) return false;
      if (statusFilter && c.status !== statusFilter) return false;
      return true;
    });
  }, [clients, search, providerFilter, statusFilter]);

  const clearFilters = () => {
    setSearch('');
    setProviderFilter('');
    setStatusFilter('');
  };

  const openAddModal = () => {
    setEditingClient(null);
    setForm({ ...defaultFormState });
    setFormErrors({});
    setModalOpen(true);
  };

  const openEditModal = (client: Client) => {
    setEditingClient(client);
    setForm({
      name: client.name,
      provider: client.provider,
      model: client.model,
      temperature: client.config.temperature,
      maxTokens: client.config.maxTokens,
      topP: client.config.topP,
      systemPrompt: client.config.systemPrompt,
    });
    setFormErrors({});
    setModalOpen(true);
  };

  const handleProviderChange = (provider: Client['provider']) => {
    const models = modelOptions[provider] ?? [];
    setForm((prev) => ({
      ...prev,
      provider,
      model: models[0] ?? '',
    }));
  };

  const validateForm = (): boolean => {
    const errors: Partial<Record<keyof ClientFormState, string>> = {};
    if (!form.name.trim()) errors.name = 'Name is required';
    if (!form.model) errors.model = 'Model is required';
    if (form.temperature < 0 || form.temperature > 2) errors.temperature = 'Must be 0-2';
    if (form.maxTokens < 1) errors.maxTokens = 'Must be at least 1';
    if (form.topP < 0 || form.topP > 1) errors.topP = 'Must be 0-1';
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) return;
    setSaving(true);
    try {
      const input: ClientInput = {
        name: form.name.trim(),
        provider: form.provider,
        model: form.model,
        status: editingClient?.status ?? 'disconnected',
        config: {
          temperature: form.temperature,
          maxTokens: form.maxTokens,
          topP: form.topP,
          systemPrompt: form.systemPrompt,
        },
      };

      if (editingClient) {
        await updateClient(editingClient.id, input);
        showToast('Client updated successfully');
      } else {
        await createClient(input);
        showToast('Client created successfully');
      }
      setModalOpen(false);
      loadClients();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to save client', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    setDeleting(true);
    try {
      await deleteClient(deleteConfirm.id);
      showToast('Client deleted successfully');
      setDeleteConfirm(null);
      loadClients();
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Failed to delete client', 'error');
    } finally {
      setDeleting(false);
    }
  };

  const columns = useMemo(() => [
    {
      key: 'name',
      header: 'Name',
      render: (row: Client) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-surface-2">
            <Server className="h-4 w-4 text-text-sub" />
          </div>
          <div>
            <p className="font-medium text-text">{row.name}</p>
            <p className="text-xs text-text-muted">{row.provider}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'model',
      header: 'Model',
      render: (row: Client) => (
        <span className="font-mono text-xs text-text-sub">{row.model}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row: Client) => {
        const variant = row.status === 'connected' ? 'success' : row.status === 'error' ? 'danger' : 'neutral';
        const label = row.status.charAt(0).toUpperCase() + row.status.slice(1);
        return <Badge variant={variant} dot>{label}</Badge>;
      },
    },
    {
      key: 'tokens',
      header: 'Tokens Today',
      render: (row: Client) => (
        <span className="text-text-sub">{formatNumber(row.usage.tokensToday)}</span>
      ),
    },
    {
      key: 'cost',
      header: 'Cost MTD',
      render: (row: Client) => (
        <span className="text-text-sub">{formatCurrency(row.usage.costMonth)}</span>
      ),
    },
    {
      key: 'lastActive',
      header: 'Last Active',
      render: (row: Client) => (
        <span className="text-text-muted">{formatLastActive(row.lastActive)}</span>
      ),
    },
    {
      key: 'actions',
      header: '',
      className: 'w-24',
      render: (row: Client) => (
        <div className="flex items-center gap-1">
          <Button
            variant="icon"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              openEditModal(row);
            }}
            title="Edit client"
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="icon"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              setDeleteConfirm(row);
            }}
            title="Delete client"
            className="text-danger hover:text-danger"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ], []);

  const isFiltered = search !== '' || providerFilter !== '' || statusFilter !== '';

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      {/* Page Header */}
      <div className="animate-fade-up flex items-start justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-text">Clients</h1>
          <p className="mt-1 text-sm text-text-muted">Manage your LLM client configurations</p>
        </div>
        <Button onClick={openAddModal}>
          <Plus className="h-4 w-4" />
          Add Client
        </Button>
      </div>

      {/* Filter Bar */}
      <div className="animate-fade-up animation-delay-60 flex items-end gap-3">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              placeholder="Search clients by name or model..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-full rounded-md border border-border bg-surface-2 pl-9 pr-3 text-[13px] text-text placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
            />
          </div>
        </div>
        <div className="w-40">
          <Select
            value={providerFilter}
            onChange={(e) => setProviderFilter(e.target.value)}
          >
            <option value="">All Providers</option>
            {providerOptions.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </Select>
        </div>
        <div className="w-36">
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Status</option>
            <option value="connected">Connected</option>
            <option value="disconnected">Disconnected</option>
            <option value="error">Error</option>
          </Select>
        </div>
        <Button variant="ghost" size="sm" onClick={clearFilters} disabled={!isFiltered}>
          Clear
        </Button>
      </div>

      {/* Table or Skeleton */}
      {loading ? (
        <div className="animate-fade-up animation-delay-120 overflow-hidden rounded-lg border border-border bg-surface">
          <div className="border-b border-border bg-surface-2 px-4 py-3">
            <div className="flex gap-4">
              {['Name', 'Model', 'Status', 'Tokens', 'Cost', 'Active', ''].map((h, i) => (
                <div key={i} className={`text-xs font-medium uppercase tracking-wide text-text-muted ${i === 0 ? 'flex-1' : 'w-24'}`}>
                  {h}
                </div>
              ))}
            </div>
          </div>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 border-b border-border px-4 py-3 last:border-b-0">
              <div className="flex flex-1 items-center gap-2.5">
                <Skeleton variant="circular" className="h-8 w-8" />
                <div className="space-y-1.5">
                  <Skeleton variant="text" className="w-24" />
                  <Skeleton variant="text" className="w-16" />
                </div>
              </div>
              <Skeleton variant="text" className="w-32" />
              <Skeleton variant="text" className="w-20" />
              <Skeleton variant="text" className="w-16" />
              <Skeleton variant="text" className="w-16" />
              <div className="w-24" />
            </div>
          ))}
        </div>
      ) : (
        <div className="animate-fade-up animation-delay-120">
          <Table
            columns={columns}
            data={filteredClients}
            getRowId={(row) => row.id}
            emptyState={
              isFiltered ? (
                <EmptyState
                  icon={<Search className="h-6 w-6" />}
                  title="No matching clients"
                  description="Try adjusting your search or filter criteria."
                  action={
                    <Button variant="secondary" size="sm" onClick={clearFilters}>
                      Clear filters
                    </Button>
                  }
                />
              ) : (
                <EmptyState
                  icon={<Server className="h-6 w-6" />}
                  title="No clients yet"
                  description="Create your first LLM client configuration to get started."
                  action={
                    <Button onClick={openAddModal}>
                      <Plus className="h-4 w-4" />
                      Add Client
                    </Button>
                  }
                />
              )
            }
          />
        </div>
      )}

      {/* Add/Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-bg/80 backdrop-blur-sm"
            onClick={() => !saving && setModalOpen(false)}
          />
          <div className="animate-fade-up relative z-10 w-full max-w-lg p-4">
            <Card>
              <CardHeader>
                <h2 className="font-display text-base font-semibold text-text">
                  {editingClient ? 'Edit Client' : 'Add Client'}
                </h2>
                <Button
                  variant="icon"
                  size="sm"
                  onClick={() => !saving && setModalOpen(false)}
                  disabled={saving}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardHeader>
              <CardBody className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <Input
                      label="Name"
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="Production API"
                      error={formErrors.name}
                    />
                  </div>
                  <div>
                    <Select
                      label="Provider"
                      value={form.provider}
                      onChange={(e) => handleProviderChange(e.target.value as Client['provider'])}
                    >
                      {providerOptions.map((p) => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Select
                      label="Model"
                      value={form.model}
                      onChange={(e) => setForm({ ...form, model: e.target.value })}
                      error={formErrors.model}
                    >
                      {(modelOptions[form.provider] ?? []).map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Input
                      label="Temperature"
                      type="number"
                      step="0.1"
                      min={0}
                      max={2}
                      value={form.temperature}
                      onChange={(e) => setForm({ ...form, temperature: Number(e.target.value) })}
                      error={formErrors.temperature}
                    />
                  </div>
                  <div>
                    <Input
                      label="Max Tokens"
                      type="number"
                      min={1}
                      value={form.maxTokens}
                      onChange={(e) => setForm({ ...form, maxTokens: Number(e.target.value) })}
                      error={formErrors.maxTokens}
                    />
                  </div>
                  <div>
                    <Input
                      label="Top P"
                      type="number"
                      step="0.05"
                      min={0}
                      max={1}
                      value={form.topP}
                      onChange={(e) => setForm({ ...form, topP: Number(e.target.value) })}
                      error={formErrors.topP}
                    />
                  </div>
                  <div className="col-span-2">
                    <div className="flex flex-col gap-1.5">
                      <label className="text-xs font-medium text-text-sub">System Prompt</label>
                      <textarea
                        className="min-h-[80px] w-full resize-y rounded-md border border-border bg-surface-2 px-3 py-2 text-[13px] text-text placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/50"
                        value={form.systemPrompt}
                        onChange={(e) => setForm({ ...form, systemPrompt: e.target.value })}
                        placeholder="You are a helpful assistant..."
                      />
                    </div>
                  </div>
                </div>

                <div className="flex justify-end gap-2 border-t border-border pt-4">
                  <Button
                    variant="ghost"
                    onClick={() => setModalOpen(false)}
                    disabled={saving}
                  >
                    Cancel
                  </Button>
                  <Button onClick={handleSave} loading={saving}>
                    {saving ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      editingClient ? 'Save Changes' : 'Create Client'
                    )}
                  </Button>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-bg/80 backdrop-blur-sm"
            onClick={() => !deleting && setDeleteConfirm(null)}
          />
          <div className="animate-fade-up relative z-10 w-full max-w-md p-4">
            <Card>
              <CardBody className="space-y-4 p-6">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-danger/12">
                    <AlertCircle className="h-5 w-5 text-danger" />
                  </div>
                  <div>
                    <h3 className="font-display text-base font-semibold text-text">Delete client?</h3>
                    <p className="mt-1 text-sm text-text-muted">
                      This will permanently delete <span className="font-medium text-text">{deleteConfirm.name}</span>. This action cannot be undone.
                    </p>
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => setDeleteConfirm(null)}
                    disabled={deleting}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="danger"
                    onClick={handleDelete}
                    loading={deleting}
                  >
                    {deleting ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Deleting...
                      </>
                    ) : (
                      <>
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </>
                    )}
                  </Button>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className="animate-fade-up fixed bottom-6 right-6 z-50">
          <Card className="border-border-strong shadow-lg">
            <CardBody className="flex items-center gap-2 p-3">
              {toast.type === 'success' ? (
                <CheckCircle2 className="h-4 w-4 text-primary" />
              ) : (
                <AlertCircle className="h-4 w-4 text-danger" />
              )}
              <span className="text-sm text-text">{toast.message}</span>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
}

export default Clients;