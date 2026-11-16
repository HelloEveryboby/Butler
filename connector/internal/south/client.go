// Package south is the connector's southbound face: it owns the DSH host
// child process (via supervisor), multiplexes tool invocations over its stdio
// stream, and surfaces registry snapshots and events back north.
//
// Call multiplexing: every invocation gets a unique ID; streaming chunks and
// terminal results are correlated by ID inside the pending map. Timeouts and
// explicit cancels emit tool.cancel south and fail the call locally without
// tearing down the connection. When the child process restarts, the codec is
// rebound and all in-flight calls are failed with ErrCodeUnavailable —
// callers decide whether to retry.
package south

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"sync"
	"time"

	"github.com/HelloEveryboby/Butler/connector/internal/proto"
	"github.com/HelloEveryboby/Butler/connector/internal/supervisor"
)

// Hooks receive south-side traffic. All hooks must be non-blocking or
// internally queued — they are invoked from the read loop.
type Hooks struct {
	// OnRegistry is called on every registry.sync frame (full snapshot).
	OnRegistry func(proto.RegistrySync)
	// OnRegistryDiff is called for incremental updates.
	OnRegistryDiff func(proto.RegistryDiff)
	// OnEvent receives session/plugin events.
	OnEvent func(proto.Event)
	// OnApprove receives approval requests that need a north-side decision.
	OnApprove func(proto.ApprovalRequest)
}

// Config configures the client.
type Config struct {
	// NodeCommand/NodeArgs launch the DSH host shim (e.g. "node", ["server.js"]).
	NodeCommand string
	NodeArgs    []string
	Env         []string // extra env (KEY=VALUE); nil inherits parent
	Dir         string   // working directory of the child

	// DefaultTimeout bounds a tool call with no per-call timeout.
	DefaultTimeout time.Duration
}

// Client maintains the southbound session.
type Client struct {
	cfg   Config
	log   *slog.Logger
	hooks Hooks

	mu       sync.Mutex
	codec    *proto.Codec
	proc     *supervisor.Process
	pending  map[string]*Call
	callSeq  uint64
	closed   bool
	readyOne sync.Once
	ready    chan struct{} // closed once the first registry.sync arrives
}

// New creates a southbound client.
func New(cfg Config, hooks Hooks, log *slog.Logger) *Client {
	if log == nil {
		log = slog.Default()
	}
	if cfg.DefaultTimeout <= 0 {
		cfg.DefaultTimeout = 2 * time.Minute
	}
	return &Client{
		cfg:     cfg,
		log:     log.With("component", "south"),
		hooks:   hooks,
		pending: make(map[string]*Call),
		ready:   make(chan struct{}),
	}
}

// Start launches the DSH host child process under supervision and binds the
// protocol codec to its stdio. Readiness is signalled via Ready().
func (c *Client) Start(ctx context.Context) error {
	c.mu.Lock()
	if c.proc != nil {
		c.mu.Unlock()
		return nil
	}
	spec := supervisor.Spec{
		Name:    "dsh-host",
		Command: c.cfg.NodeCommand,
		Args:    c.cfg.NodeArgs,
		Env:     c.cfg.Env,
		Dir:     c.cfg.Dir,
		Attach:  c.bind,
	}
	proc := supervisor.New(spec, c.log)
	proc.OnStateChange = func(s supervisor.State) {
		c.log.Info("dsh host state", "state", s.String())
		if s == supervisor.StateFailed {
			// Fail everything: the connection is not coming back.
			c.failAll(proto.NewError(proto.ErrCodeUnavailable, "dsh host failed permanently", nil))
		}
	}
	c.proc = proc
	c.mu.Unlock()
	return proc.Start(ctx)
}

// AttachStream wires an arbitrary stream (tests, socket mode) instead of a
// child process. Must be called before any Invoke.
func (c *Client) AttachStream(stream io.ReadWriteCloser) {
	c.bindStream(proto.NewCodec(stream))
}

// Ready returns a channel closed after the initial registry.sync arrives.
func (c *Client) Ready() <-chan struct{} { return c.ready }

// Invoke dispatches a tool call and returns its streaming handle. The call is
// bound to ctx: cancellation sends tool.cancel south and fails the call.
func (c *Client) Invoke(ctx context.Context, inv proto.ToolInvoke) (*Call, error) {
	c.mu.Lock()
	if c.closed || c.codec == nil {
		c.mu.Unlock()
		return nil, proto.NewError(proto.ErrCodeUnavailable, "southbound not connected", nil)
	}
	c.callSeq++
	id := fmt.Sprintf("call-%d", c.callSeq)
	call := &Call{
		ID:     id,
		chunks: make(chan proto.ToolChunk, 16),
		done:   make(chan struct{}),
	}
	c.pending[id] = call
	codec := c.codec
	timeout := c.cfg.DefaultTimeout
	if inv.TimeoutMs > 0 {
		timeout = time.Duration(inv.TimeoutMs) * time.Millisecond
	}
	c.mu.Unlock()

	frame, err := proto.NewFrame(id, proto.TypeToolInvoke, inv)
	if err != nil {
		c.removePending(id)
		return nil, err
	}
	if err := codec.WriteFrame(frame); err != nil {
		c.removePending(id)
		return nil, proto.NewError(proto.ErrCodeUpstream, "write invoke: "+err.Error(), nil)
	}

	// Timeout / cancellation watchdog.
	go func() {
		timer := time.NewTimer(timeout)
		defer timer.Stop()
		select {
		case <-call.done:
		case <-timer.C:
			c.fail(call, proto.NewError(proto.ErrCodeTimeout, fmt.Sprintf("tool %s timed out after %s", inv.Tool, timeout), nil))
			c.sendCancel(id, "timeout")
		case <-ctx.Done():
			c.fail(call, proto.NewError(proto.ErrCodeCancelled, "cancelled: "+ctx.Err().Error(), nil))
			c.sendCancel(id, "cancelled")
		}
	}()
	return call, nil
}

// Cancel aborts an in-flight call by ID.
func (c *Client) Cancel(id, reason string) {
	c.mu.Lock()
	call, ok := c.pending[id]
	c.mu.Unlock()
	if ok {
		c.fail(call, proto.NewError(proto.ErrCodeCancelled, reason, nil))
		c.sendCancel(id, reason)
	}
}

// sendCancel emits a best-effort tool.cancel frame.
func (c *Client) sendCancel(id, reason string) {
	if f, err := proto.NewFrame(id, proto.TypeToolCancel, proto.ToolCancel{Reason: reason}); err == nil {
		_ = c.writeControl(f)
	}
}

// AnswerApproval forwards a north-side approval decision to the DSH host.
func (c *Client) AnswerApproval(d proto.ApprovalDecision) error {
	f, err := proto.NewFrame(d.RequestID, proto.TypeApproveAnswer, d)
	if err != nil {
		return err
	}
	return c.writeControl(f)
}

// Ping probes liveness of the south side.
func (c *Client) Ping(ctx context.Context) error {
	id := fmt.Sprintf("ping-%d", time.Now().UnixNano())
	call := &Call{ID: id, done: make(chan struct{})}
	c.mu.Lock()
	if c.closed || c.codec == nil {
		c.mu.Unlock()
		return proto.NewError(proto.ErrCodeUnavailable, "southbound not connected", nil)
	}
	c.pending[id] = call
	c.mu.Unlock()
	defer c.removePending(id)

	f, _ := proto.NewFrame(id, proto.TypeHealthPing, nil)
	if err := c.writeControl(f); err != nil {
		return err
	}
	select {
	case <-call.done:
		return nil
	case <-time.After(5 * time.Second):
		return proto.NewError(proto.ErrCodeTimeout, "ping timeout", nil)
	case <-ctx.Done():
		return ctx.Err()
	}
}

// Close terminates the southbound session and fails all in-flight calls.
func (c *Client) Close() error {
	c.mu.Lock()
	if c.closed {
		c.mu.Unlock()
		return nil
	}
	c.closed = true
	proc := c.proc
	c.mu.Unlock()

	c.failAll(proto.NewError(proto.ErrCodeUnavailable, "southbound closed", nil))
	var err error
	if proc != nil {
		err = proc.Stop()
	}
	return err
}

// ---- streaming call handle ----

// Call is a streaming handle to one in-flight tool invocation.
type Call struct {
	ID     string
	chunks chan proto.ToolChunk
	done   chan struct{}

	mu     sync.Mutex
	result proto.ToolResult
	err    *proto.ProtoError
}

// Chunks streams partial results. The channel is closed when the call is
// terminal (result or error).
func (c *Call) Chunks() <-chan proto.ToolChunk { return c.chunks }

// Result blocks until the call is terminal and returns the final outcome.
func (c *Call) Result(ctx context.Context) (proto.ToolResult, error) {
	select {
	case <-c.done:
		c.mu.Lock()
		defer c.mu.Unlock()
		if c.err != nil {
			return c.result, c.err
		}
		return c.result, nil
	case <-ctx.Done():
		return proto.ToolResult{}, ctx.Err()
	}
}

func (c *Call) finish(res proto.ToolResult, pe *proto.ProtoError) {
	c.mu.Lock()
	if pe == nil {
		c.result = res
	} else {
		c.err = pe
	}
	c.mu.Unlock()
	if c.chunks != nil {
		close(c.chunks)
	}
	close(c.done)
}

// ---- internals ----

// bind is the supervisor Attach callback: (re)bind the codec on every child
// (re)start.
func (c *Client) bind(stdin io.WriteCloser, stdout io.ReadCloser) {
	c.bindStream(proto.NewCodec(&stdioStream{r: stdout, w: stdin}))
}

func (c *Client) bindStream(codec *proto.Codec) {
	c.mu.Lock()
	old := c.codec
	c.codec = codec
	c.closed = false
	pending := c.pending
	c.pending = make(map[string]*Call)
	c.mu.Unlock()

	for _, call := range pending {
		call.finish(proto.ToolResult{}, proto.NewError(proto.ErrCodeUnavailable, "connection rebound", nil))
	}
	if old != nil {
		_ = old.Close()
	}
	go c.readLoop()
}

// readLoop is the single reader of the south stream; it demultiplexes frames
// into pending calls and hooks.
func (c *Client) readLoop() {
	for {
		c.mu.Lock()
		codec := c.codec
		c.mu.Unlock()
		if codec == nil {
			return
		}
		frame, err := codec.ReadFrame()
		if err != nil {
			c.log.Warn("south stream closed", "err", err)
			c.failAll(proto.NewError(proto.ErrCodeUnavailable, "south stream closed: "+err.Error(), nil))
			return
		}
		c.dispatch(frame)
	}
}

func (c *Client) dispatch(f *proto.Frame) {
	switch f.Type {
	case proto.TypeToolChunk:
		var chunk proto.ToolChunk
		if err := f.DecodePayload(&chunk); err != nil {
			c.log.Warn("bad chunk frame", "err", err)
			return
		}
		c.mu.Lock()
		call := c.pending[f.ID]
		c.mu.Unlock()
		if call != nil && call.chunks != nil {
			select {
			case call.chunks <- chunk:
			default: // consumer too slow: drop chunk, result still arrives
				c.log.Warn("chunk dropped (slow consumer)", "call", f.ID, "seq", chunk.Seq)
			}
		}

	case proto.TypeToolResult:
		var res proto.ToolResult
		if err := f.DecodePayload(&res); err != nil {
			c.log.Warn("bad result frame", "err", err)
			return
		}
		c.mu.Lock()
		call := c.pending[f.ID]
		delete(c.pending, f.ID)
		c.mu.Unlock()
		if call != nil {
			call.finish(res, nil)
		}

	case proto.TypeError:
		c.mu.Lock()
		call := c.pending[f.ID]
		delete(c.pending, f.ID)
		c.mu.Unlock()
		if call != nil {
			pe := f.Error
			if pe == nil {
				pe = proto.NewError(proto.ErrCodeUpstream, "unspecified upstream error", nil)
			}
			call.finish(proto.ToolResult{}, pe)
		}

	case proto.TypeHealthPong:
		c.mu.Lock()
		call := c.pending[f.ID]
		delete(c.pending, f.ID)
		c.mu.Unlock()
		if call != nil {
			call.finish(proto.ToolResult{}, nil)
		}

	case proto.TypeRegistrySync:
		var snap proto.RegistrySync
		if err := f.DecodePayload(&snap); err != nil {
			c.log.Warn("bad registry.sync", "err", err)
			return
		}
		c.readyOne.Do(func() { close(c.ready) })
		if c.hooks.OnRegistry != nil {
			c.hooks.OnRegistry(snap)
		}

	case proto.TypeRegistryDiff:
		var diff proto.RegistryDiff
		if err := f.DecodePayload(&diff); err != nil {
			c.log.Warn("bad registry.diff", "err", err)
			return
		}
		if c.hooks.OnRegistryDiff != nil {
			c.hooks.OnRegistryDiff(diff)
		}

	case proto.TypeEventPush:
		var ev proto.Event
		if err := f.DecodePayload(&ev); err != nil {
			c.log.Warn("bad event.push", "err", err)
			return
		}
		if c.hooks.OnEvent != nil {
			c.hooks.OnEvent(ev)
		}

	case proto.TypeApproveAsk:
		var req proto.ApprovalRequest
		if err := f.DecodePayload(&req); err != nil {
			c.log.Warn("bad approve.ask", "err", err)
			return
		}
		if c.hooks.OnApprove != nil {
			c.hooks.OnApprove(req)
		}

	default:
		c.log.Warn("unhandled south frame", "type", f.Type)
		_ = c.writeControl(&proto.Frame{
			ID:    f.ID,
			Type:  proto.TypeError,
			Done:  true,
			Error: proto.NewError(proto.ErrCodeUnsupported, "unsupported frame "+string(f.Type), nil),
		})
	}
}

func (c *Client) fail(call *Call, pe *proto.ProtoError) {
	c.removePending(call.ID)
	call.finish(proto.ToolResult{}, pe)
}

func (c *Client) failAll(pe *proto.ProtoError) {
	c.mu.Lock()
	pending := c.pending
	c.pending = make(map[string]*Call)
	c.mu.Unlock()
	for _, call := range pending {
		call.finish(proto.ToolResult{}, pe)
	}
}

func (c *Client) removePending(id string) {
	c.mu.Lock()
	delete(c.pending, id)
	c.mu.Unlock()
}

func (c *Client) writeControl(f *proto.Frame) error {
	c.mu.Lock()
	codec := c.codec
	c.mu.Unlock()
	if codec == nil {
		return proto.NewError(proto.ErrCodeUnavailable, "southbound not connected", nil)
	}
	return codec.WriteFrame(f)
}

// stdioStream adapts child-process pipes to io.ReadWriteCloser.
type stdioStream struct {
	r io.ReadCloser
	w io.WriteCloser
}

func (s *stdioStream) Read(p []byte) (int, error)  { return s.r.Read(p) }
func (s *stdioStream) Write(p []byte) (int, error) { return s.w.Write(p) }
func (s *stdioStream) Close() error {
	werr := s.w.Close()
	rerr := s.r.Close()
	if werr != nil {
		return werr
	}
	return rerr
}
