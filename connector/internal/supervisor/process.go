// Package supervisor manages the DSH host child process: launch, health
// tracking, crash recovery with exponential backoff and jitter, restart
// budgeting, and graceful shutdown. It is deliberately process-agnostic —
// the same supervisor runs the Node host today and any future BHL link.
//
// On every (re)start the supervisor hands the child's stdio to Spec.Attach,
// so consumers can (re)bind their protocol codec without owning process
// lifecycle details.
package supervisor

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"math/rand/v2"
	"os/exec"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

// State is the lifecycle state of the supervised process.
type State int32

const (
	StateStopped State = iota
	StateStarting
	StateHealthy
	StateDegraded
	StateFailed // restart budget exhausted; needs operator attention
)

// String implements fmt.Stringer.
func (s State) String() string {
	switch s {
	case StateStopped:
		return "stopped"
	case StateStarting:
		return "starting"
	case StateHealthy:
		return "healthy"
	case StateDegraded:
		return "degraded"
	case StateFailed:
		return "failed"
	}
	return "unknown"
}

// Spec configures the child process.
type Spec struct {
	Name    string   // human-readable, e.g. "dsh-host"
	Command string   // executable, e.g. "node"
	Args    []string // e.g. ["lib_external/dsh-host/server.js"]
	Env     []string // additional environment (KEY=VALUE); nil inherits parent
	Dir     string   // working directory

	// Attach, when set, receives the child's stdin/stdout immediately after
	// every successful start (including restarts). Streams are owned by the
	// consumer; they are closed when the process dies.
	Attach func(stdin io.WriteCloser, stdout io.ReadCloser)

	// RestartBudget is the maximum number of restarts allowed inside
	// RestartWindow before the supervisor gives up (StateFailed).
	RestartBudget int
	RestartWindow time.Duration
	// StopGrace is how long a SIGTERM gets before SIGKILL.
	StopGrace time.Duration
}

// withDefaults normalizes the spec.
func (s Spec) withDefaults() Spec {
	out := s
	if out.RestartBudget <= 0 {
		out.RestartBudget = 5
	}
	if out.RestartWindow <= 0 {
		out.RestartWindow = 2 * time.Minute
	}
	if out.StopGrace <= 0 {
		out.StopGrace = 5 * time.Second
	}
	return out
}

// Process supervises one child.
type Process struct {
	spec Spec
	log  *slog.Logger

	mu       sync.Mutex
	cancel   context.CancelFunc // cancels the supervise loop
	done     chan struct{}      // closed when the supervise loop exits
	restarts []time.Time        // restart timestamps inside the window
	stopping bool

	state atomic.Int32

	// OnStateChange, if set before Start, observes every transition.
	OnStateChange func(State)
}

// New builds a supervisor for the given spec.
func New(spec Spec, log *slog.Logger) *Process {
	if log == nil {
		log = slog.Default()
	}
	p := &Process{spec: spec.withDefaults(), log: log.With("supervised", spec.Name)}
	p.state.Store(int32(StateStopped))
	return p
}

// State returns the current lifecycle state.
func (p *Process) State() State { return State(p.state.Load()) }

// Start launches the child and begins supervision. It returns after the
// first spawn has been initiated; failures surface through state transitions
// and logs. Calling Start twice is a no-op while running.
func (p *Process) Start(ctx context.Context) error {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.done != nil {
		return nil // already running
	}
	runCtx, cancel := context.WithCancel(context.WithoutCancel(ctx))
	p.cancel = cancel
	p.done = make(chan struct{})
	p.stopping = false
	go p.supervise(runCtx)
	return nil
}

// Stop gracefully terminates the child and ends supervision. It is safe to
// call multiple times and blocks until the supervise loop exits.
func (p *Process) Stop() error {
	p.mu.Lock()
	if p.done == nil {
		p.mu.Unlock()
		return nil
	}
	p.stopping = true
	done := p.done
	cancel := p.cancel
	p.mu.Unlock()

	if cancel != nil {
		cancel()
	}
	<-done

	p.mu.Lock()
	p.done = nil
	p.cancel = nil
	p.mu.Unlock()
	p.setState(StateStopped)
	return nil
}

// supervise is the restart loop. It owns the child process lifecycle.
func (p *Process) supervise(ctx context.Context) {
	defer close(p.done)
	backoff := 500 * time.Millisecond
	const maxBackoff = 30 * time.Second

	for {
		p.setState(StateStarting)
		cmd := p.buildCmd(ctx)

		var stdin io.WriteCloser
		var stdout io.ReadCloser
		if p.spec.Attach != nil {
			var err error
			if stdin, err = cmd.StdinPipe(); err != nil {
				p.log.Error("stdin pipe failed", "err", err)
				return
			}
			if stdout, err = cmd.StdoutPipe(); err != nil {
				p.log.Error("stdout pipe failed", "err", err)
				return
			}
		}
		stderr, _ := cmd.StderrPipe()

		if err := cmd.Start(); err != nil {
			p.log.Error("start failed", "err", err)
		} else {
			p.log.Info("child started", "pid", cmd.Process.Pid)
			if p.spec.Attach != nil && stdin != nil && stdout != nil {
				p.spec.Attach(stdin, stdout)
			}
			if stderr != nil {
				go p.drainStderr(stderr)
			}
			p.setState(StateHealthy)
			err = cmd.Wait()
			p.log.Warn("child exited", "err", err)
		}

		p.mu.Lock()
		stopping := p.stopping
		p.mu.Unlock()
		if stopping || ctx.Err() != nil {
			return
		}

		// Crash recovery: enforce the restart budget.
		now := time.Now()
		p.mu.Lock()
		p.restarts = append(p.restarts, now)
		window := now.Add(-p.spec.RestartWindow)
		kept := p.restarts[:0]
		for _, t := range p.restarts {
			if t.After(window) {
				kept = append(kept, t)
			}
		}
		p.restarts = kept
		budgetLeft := p.spec.RestartBudget - len(p.restarts)
		p.mu.Unlock()

		if budgetLeft <= 0 {
			p.log.Error("restart budget exhausted", "window", p.spec.RestartWindow, "budget", p.spec.RestartBudget)
			p.setState(StateFailed)
			return
		}

		p.setState(StateDegraded)
		half := backoff / 2
		sleep := half + time.Duration(rand.Int64N(int64(half)+1)) // jittered
		p.log.Info("restarting", "in", sleep, "budgetLeft", budgetLeft)
		select {
		case <-time.After(sleep):
		case <-ctx.Done():
			return
		}
		backoff *= 2
		if backoff > maxBackoff {
			backoff = maxBackoff
		}
	}
}

// buildCmd constructs the child command with graceful-kill semantics.
func (p *Process) buildCmd(ctx context.Context) *exec.Cmd {
	cmd := exec.CommandContext(ctx, p.spec.Command, p.spec.Args...)
	cmd.Dir = p.spec.Dir
	if p.spec.Env != nil {
		cmd.Env = p.spec.Env
	}
	// On timeout/cancel: SIGTERM first, escalate after StopGrace.
	cmd.WaitDelay = p.spec.StopGrace
	cmd.Cancel = func() error {
		return cmd.Process.Signal(syscall.SIGTERM)
	}
	return cmd
}

// drainStderr routes child diagnostics into the supervisor log at error level.
func (p *Process) drainStderr(r io.Reader) {
	buf := make([]byte, 4096)
	for {
		n, err := r.Read(buf)
		if n > 0 {
			p.log.Error("child stderr", "line", string(buf[:n]))
		}
		if err != nil {
			if !errors.Is(err, io.EOF) {
				p.log.Debug("stderr closed", "err", err)
			}
			return
		}
	}
}

func (p *Process) setState(s State) {
	prev := State(p.state.Swap(int32(s)))
	if prev == s {
		return
	}
	p.log.Info("state change", "from", prev.String(), "to", s.String())
	if p.OnStateChange != nil {
		p.OnStateChange(s)
	}
}

// String renders a status summary for health endpoints.
func (p *Process) String() string {
	return fmt.Sprintf("%s: %s", p.spec.Name, p.State())
}
