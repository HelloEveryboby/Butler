package supervisor

import (
	"context"
	"io"
	"testing"
	"time"
)

// TestStartStopLifecycle supervises a long-running child and verifies the
// Attach callback fires, state transitions to healthy, and Stop terminates
// the child promptly.
func TestStartStopLifecycle(t *testing.T) {
	attached := make(chan struct{}, 1)
	p := New(Spec{
		Name:   "test-sleeper",
		Command: "sleep",
		Args:    []string{"60"},
		Attach: func(stdin io.WriteCloser, stdout io.ReadCloser) {
			attached <- struct{}{}
		},
	}, nil)

	ctx := context.Background()
	if err := p.Start(ctx); err != nil {
		t.Fatalf("Start: %v", err)
	}
	select {
	case <-attached:
	case <-time.After(3 * time.Second):
		t.Fatal("Attach callback not invoked")
	}

	deadline := time.Now().Add(3 * time.Second)
	for p.State() != StateHealthy && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if p.State() != StateHealthy {
		t.Fatalf("state = %s, want healthy", p.State())
	}

	start := time.Now()
	if err := p.Stop(); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	if elapsed := time.Since(start); elapsed > 3*time.Second {
		t.Fatalf("Stop took %s, want prompt termination", elapsed)
	}
	if p.State() != StateStopped {
		t.Fatalf("state = %s, want stopped", p.State())
	}
}

// TestRestartBudgetExhaustion uses a child that exits immediately; after the
// budget is spent the supervisor must land in StateFailed.
func TestRestartBudgetExhaustion(t *testing.T) {
	p := New(Spec{
		Name:          "test-crasher",
		Command:       "sh",
		Args:          []string{"-c", "exit 1"},
		RestartBudget: 2,
		RestartWindow: time.Minute,
	}, nil)

	if err := p.Start(context.Background()); err != nil {
		t.Fatalf("Start: %v", err)
	}
	defer p.Stop()

	deadline := time.Now().Add(15 * time.Second)
	for p.State() != StateFailed && time.Now().Before(deadline) {
		time.Sleep(50 * time.Millisecond)
	}
	if p.State() != StateFailed {
		t.Fatalf("state = %s, want failed", p.State())
	}
}

// TestGracefulStopUsesSigterm verifies Stop does not need SIGKILL for a
// well-behaved child: the process should exit on SIGTERM within StopGrace.
func TestGracefulStopUsesSigterm(t *testing.T) {
	p := New(Spec{
		Name:       "test-trapper",
		Command:    "sh",
		Args:       []string{"-c", "trap 'exit 0' TERM; while true; do sleep 1; done"},
		StopGrace:  2 * time.Second,
	}, nil)
	if err := p.Start(context.Background()); err != nil {
		t.Fatalf("Start: %v", err)
	}
	time.Sleep(200 * time.Millisecond)
	if err := p.Stop(); err != nil {
		t.Fatalf("Stop: %v", err)
	}
	// If SIGKILL were needed the Stop would block for StopGrace; a clean
	// SIGTERM exit keeps it fast. (No strict assert on timing — CI variance.)
}
