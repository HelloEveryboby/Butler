package registry

import (
	"testing"

	"github.com/HelloEveryboby/Butler/connector/internal/proto"
)

func cap(name, source string) proto.Capability {
	return proto.Capability{
		Name:        name,
		Description: "tool " + name,
		Risk:        proto.RiskReadOnly,
		Source:      source,
	}
}

func TestUpsertAndSnapshot(t *testing.T) {
	r := New()
	v, err := r.Upsert(cap("b", "p1"), cap("a", "p2"))
	if err != nil {
		t.Fatalf("Upsert: %v", err)
	}
	if v != 1 {
		t.Fatalf("version = %d, want 1", v)
	}
	snap := r.Snapshot()
	if snap.Version != 1 || len(snap.Capabilities) != 2 {
		t.Fatalf("snapshot = %+v", snap)
	}
	if snap.Capabilities[0].Name != "a" || snap.Capabilities[1].Name != "b" {
		t.Fatalf("snapshot not sorted: %+v", snap.Capabilities)
	}
}

func TestDiffSince(t *testing.T) {
	r := New()
	r.Upsert(cap("a", "p1"))
	v2, _ := r.Upsert(cap("b", "p1"))
	r.Remove("a")
	r.Upsert(cap("c", "p1"))

	diff, ok := r.DiffSince(v2)
	if !ok {
		t.Fatal("DiffSince should succeed inside tombstone window")
	}
	if len(diff.Upserts) != 1 || diff.Upserts[0].Name != "c" {
		t.Fatalf("upserts = %+v", diff.Upserts)
	}
	if len(diff.Removals) != 1 || diff.Removals[0] != "a" {
		t.Fatalf("removals = %+v", diff.Removals)
	}
	if diff.To != r.Version() {
		t.Fatalf("diff.To = %d, want %d", diff.To, r.Version())
	}
}

func TestDiffSinceFutureVersion(t *testing.T) {
	r := New()
	r.Upsert(cap("a", "p1"))
	if _, ok := r.DiffSince(r.Version() + 10); ok {
		t.Fatal("diff from the future must require resync")
	}
}

func TestReplaceResync(t *testing.T) {
	r := New()
	r.Upsert(cap("old1", "p"), cap("old2", "p"))
	v, err := r.Replace([]proto.Capability{cap("new1", "p")})
	if err != nil {
		t.Fatalf("Replace: %v", err)
	}
	if r.Len() != 1 {
		t.Fatalf("len = %d, want 1", r.Len())
	}
	diff, ok := r.DiffSince(v - 1)
	if !ok {
		t.Fatal("diff should be available")
	}
	found := false
	for _, n := range diff.Removals {
		if n == "old1" {
			found = true
		}
	}
	if !found {
		t.Fatalf("removals missing old1: %+v", diff.Removals)
	}
}

func TestValidateRejectsBadCapability(t *testing.T) {
	r := New()
	if _, err := r.Upsert(proto.Capability{Name: ""}); err == nil {
		t.Fatal("expected validation error")
	}
	if r.Len() != 0 {
		t.Fatal("invalid capability must not be stored")
	}
}

func TestDiffAfterTombstoneExpiry(t *testing.T) {
	r := New()
	r.Upsert(cap("a", "p"))
	r.Remove("a")
	// Force version past the tombstone window with cheap upserts.
	for i := 0; i < tombstoneWindow+2; i++ {
		r.Upsert(cap("filler", "p"))
	}
	if _, ok := r.DiffSince(1); ok {
		// Only assert when the tombstone has actually been pruned.
		if _, gone := r.tombstones["a"]; gone {
			t.Fatal("tombstone should be pruned past the window")
		}
	}
}
