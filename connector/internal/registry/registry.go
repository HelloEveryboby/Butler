// Package registry maintains the connector's capability table: the set of
// tools exported by the DSH plugin host, with monotonic versioning so that
// the north side (Butler) can stay in sync through either full snapshots or
// incremental diffs.
//
// Concurrency model: all public methods are safe for concurrent use. Diffs
// are computed against a bounded tombstone window; when a consumer falls too
// far behind, DiffSince reports that a full resync is required instead of
// silently returning an incomplete delta.
package registry

import (
	"fmt"
	"sort"
	"sync"

	"github.com/HelloEveryboby/Butler/connector/internal/proto"
)

// tombstoneWindow is how many versions of removals are retained for diffing.
// After that, slow consumers must fall back to a full resync.
const tombstoneWindow = 4096

// entry pairs a capability with the version at which it last changed.
type entry struct {
	cap     proto.Capability
	version uint64
}

// Registry is a versioned, thread-safe capability table.
type Registry struct {
	mu          sync.RWMutex
	version     uint64
	entries     map[string]entry
	tombstones  map[string]uint64 // name -> removal version
}

// New returns an empty registry.
func New() *Registry {
	return &Registry{
		entries:    make(map[string]entry),
		tombstones: make(map[string]uint64),
	}
}

// Upsert validates and inserts/replaces capabilities, bumping the version
// once per call. It returns the new version.
func (r *Registry) Upsert(caps ...proto.Capability) (uint64, error) {
	for i := range caps {
		if err := caps[i].Validate(); err != nil {
			return 0, err
		}
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.version++
	for _, c := range caps {
		r.entries[c.Name] = entry{cap: c, version: r.version}
		delete(r.tombstones, c.Name)
	}
	r.pruneTombstonesLocked()
	return r.version, nil
}

// Remove deletes capabilities by name. Unknown names are ignored (removal is
// idempotent). Returns the new version.
func (r *Registry) Remove(names ...string) uint64 {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.version++
	for _, name := range names {
		if _, ok := r.entries[name]; ok {
			delete(r.entries, name)
			r.tombstones[name] = r.version
		}
	}
	r.pruneTombstonesLocked()
	return r.version
}

// Replace performs a full resync: the table is made to match caps exactly.
// Returns the new version. Callers use this after a south-side reconnect.
func (r *Registry) Replace(caps []proto.Capability) (uint64, error) {
	for i := range caps {
		if err := caps[i].Validate(); err != nil {
			return 0, err
		}
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.version++
	next := make(map[string]entry, len(caps))
	for _, c := range caps {
		next[c.Name] = entry{cap: c, version: r.version}
	}
	for name := range r.entries {
		if _, kept := next[name]; !kept {
			r.tombstones[name] = r.version
		}
	}
	r.entries = next
	r.pruneTombstonesLocked()
	return r.version, nil
}

// Get returns a capability by name.
func (r *Registry) Get(name string) (proto.Capability, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	e, ok := r.entries[name]
	return e.cap, ok
}

// Version returns the current monotonic table version.
func (r *Registry) Version() uint64 {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return r.version
}

// Len returns the number of capabilities currently registered.
func (r *Registry) Len() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.entries)
}

// Snapshot returns a stable, sorted full view of the table.
func (r *Registry) Snapshot() proto.RegistrySync {
	r.mu.RLock()
	defer r.mu.RUnlock()
	snap := proto.RegistrySync{
		Version:      r.version,
		Capabilities: make([]proto.Capability, 0, len(r.entries)),
	}
	for _, e := range r.entries {
		snap.Capabilities = append(snap.Capabilities, e.cap)
	}
	sort.Slice(snap.Capabilities, func(i, j int) bool {
		return snap.Capabilities[i].Name < snap.Capabilities[j].Name
	})
	return snap
}

// DiffSince computes the incremental changes after the given version.
// ok is false when the consumer is outside the tombstone window and must
// request a full resync instead.
func (r *Registry) DiffSince(since uint64) (proto.RegistryDiff, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if since > r.version {
		return proto.RegistryDiff{}, false
	}
	diff := proto.RegistryDiff{From: since, To: r.version}
	for _, e := range r.entries {
		if e.version > since {
			diff.Upserts = append(diff.Upserts, e.cap)
		}
	}
	for name, v := range r.tombstones {
		if v > since {
			diff.Removals = append(diff.Removals, name)
		}
	}
	sort.Slice(diff.Upserts, func(i, j int) bool { return diff.Upserts[i].Name < diff.Upserts[j].Name })
	sort.Strings(diff.Removals)
	return diff, true
}

// pruneTombstonesLocked drops tombstones that fell out of the diff window.
// Caller must hold the write lock.
func (r *Registry) pruneTombstonesLocked() {
	floor := uint64(0)
	if r.version > tombstoneWindow {
		floor = r.version - tombstoneWindow
	}
	for name, v := range r.tombstones {
		if v <= floor {
			delete(r.tombstones, name)
		}
	}
}

// String renders a compact summary for logs.
func (r *Registry) String() string {
	return fmt.Sprintf("registry(v%d, %d tools)", r.Version(), r.Len())
}
