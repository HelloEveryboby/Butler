// Package north is the connector's northbound face: a framed JSON-RPC server
// that Butler (Python) connects to. It exposes the capability registry,
// proxies tool invocations to the DSH host (south), relays approval
// questions and decisions, and broadcasts session/plugin events.
//
// Concurrency: one goroutine per connection read loop; invocation handlers
// run per call so slow tools never block other traffic on the same
// connection. All writes go through proto.Codec's write lock.
package north

import (
	"context"
	"log/slog"
	"sync"
	"time"

	"github.com/HelloEveryboby/Butler/connector/internal/approval"
	"github.com/HelloEveryboby/Butler/connector/internal/events"
	"github.com/HelloEveryboby/Butler/connector/internal/proto"
	"github.com/HelloEveryboby/Butler/connector/internal/registry"
	"github.com/HelloEveryboby/Butler/connector/internal/south"
	"github.com/HelloEveryboby/Butler/connector/internal/transport"
)

// Server accepts and serves north-side connections.
type Server struct {
	log   *slog.Logger
	ln    transport.Listener
	reg   *registry.Registry
	pump  *events.Pump
	proxy *approval.Proxy
	south *south.Client

	// AskTimeout bounds interactive approval round-trips.
	AskTimeout time.Duration

	mu       sync.Mutex
	conns    map[*conn]struct{}
	askWait  map[string]chan proto.ApprovalDecision
}

// New wires a northbound server. The approval proxy's AskFunc is bound here:
// policy "ask" verdicts surface as approve.ask frames to the originating
// Butler connection.
func New(
	ln transport.Listener,
	reg *registry.Registry,
	pump *events.Pump,
	southClient *south.Client,
	log *slog.Logger,
	askTimeout time.Duration,
) *Server {
	if log == nil {
		log = slog.Default()
	}
	if askTimeout <= 0 {
		askTimeout = 30 * time.Second
	}
	s := &Server{
		log:        log.With("component", "north"),
		ln:         ln,
		reg:        reg,
		pump:       pump,
		south:      southClient,
		AskTimeout: askTimeout,
		conns:      make(map[*conn]struct{}),
		askWait:    make(map[string]chan proto.ApprovalDecision),
	}
	s.proxy = approval.NewProxy(approval.Default(), s.askOrigin, nil, askTimeout)
	return s
}

// Proxy exposes the approval proxy (configuration can be layered before Serve).
func (s *Server) Proxy() *approval.Proxy { return s.proxy }

// Ask implements approval.AskFunc publicly so callers can compose custom
// proxies around the same northbound approval round-trip.
func (s *Server) Ask(ctx context.Context, req proto.ApprovalRequest) (proto.ApprovalDecision, error) {
	return s.askOrigin(ctx, req)
}

// Broadcast sends a frame to every connected Butler console.
func (s *Server) Broadcast(f *proto.Frame) { s.broadcast(f) }

// SetProxy replaces the approval proxy (e.g. with a custom policy + audit log).
func (s *Server) SetProxy(p *approval.Proxy) { s.proxy = p }

// Serve accepts connections until the context is cancelled or the listener
// fails. Event broadcast runs until ctx is done.
func (s *Server) Serve(ctx context.Context) error {
	go s.broadcastEvents(ctx)

	go func() {
		<-ctx.Done()
		_ = s.ln.Close()
	}()

	for {
		stream, err := s.ln.Accept()
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			return err
		}
		c := &conn{codec: proto.NewCodec(stream), log: s.log}
		s.mu.Lock()
		s.conns[c] = struct{}{}
		s.mu.Unlock()
		go s.serveConn(ctx, c)
	}
}

// BroadcastRegistry pushes a full capability snapshot to every connection.
// Called after south-side registry changes.
func (s *Server) BroadcastRegistry() {
	snap := s.reg.Snapshot()
	frame, err := proto.NewFrame("registry-broadcast", proto.TypeRegistrySync, snap)
	if err != nil {
		return
	}
	s.broadcast(frame)
}

// ---- connection handling ----

type conn struct {
	codec *proto.Codec
	log   *slog.Logger

	closeOnce sync.Once
}

func (c *conn) close() {
	c.closeOnce.Do(func() { _ = c.codec.Close() })
}

func (s *Server) serveConn(ctx context.Context, c *conn) {
	defer func() {
		c.close()
		s.mu.Lock()
		delete(s.conns, c)
		s.mu.Unlock()
		s.log.Info("butler disconnected")
	}()
	s.log.Info("butler connected")

	for {
		select {
		case <-ctx.Done():
			return
		default:
		}
		frame, err := c.codec.ReadFrame()
		if err != nil {
			s.log.Debug("north read closed", "err", err)
			return
		}
		s.handleFrame(ctx, c, frame)
	}
}

func (s *Server) handleFrame(ctx context.Context, c *conn, f *proto.Frame) {
	switch f.Type {
	case proto.TypeToolInvoke:
		go s.handleInvoke(ctx, c, f)

	case proto.TypeToolCancel:
		var cancel proto.ToolCancel
		_ = f.DecodePayload(&cancel)
		s.south.Cancel(f.ID, cancel.Reason)

	case proto.TypeRegistrySync:
		// Full-state request from Butler.
		snap := s.reg.Snapshot()
		reply, err := proto.NewFrame(f.ID, proto.TypeRegistrySync, snap)
		if err == nil {
			_ = c.codec.WriteFrame(reply)
		}

	case proto.TypeApproveAnswer:
		var d proto.ApprovalDecision
		if err := f.DecodePayload(&d); err != nil {
			_ = c.codec.WriteError(f.ID, proto.NewError(proto.ErrCodeMalformed, "bad approve.answer", nil))
			return
		}
		s.deliverAnswer(c, d)

	case proto.TypeHealthPing:
		pong, _ := proto.NewFrame(f.ID, proto.TypeHealthPong, nil)
		_ = c.codec.WriteFrame(pong)

	default:
		_ = c.codec.WriteError(f.ID, proto.NewError(proto.ErrCodeUnsupported, "unsupported frame "+string(f.Type), nil))
	}
}

// handleInvoke runs one tool call end-to-end: resolve, approve, dispatch,
// stream chunks north, deliver the terminal result.
func (s *Server) handleInvoke(ctx context.Context, c *conn, f *proto.Frame) {
	var inv proto.ToolInvoke
	if err := f.DecodePayload(&inv); err != nil {
		_ = c.codec.WriteError(f.ID, proto.NewError(proto.ErrCodeMalformed, "bad tool.invoke: "+err.Error(), nil))
		return
	}

	// Resolve the capability. The registry — not the caller — is the source
	// of truth for risk classification and provenance.
	capEntry, ok := s.reg.Get(inv.Tool)
	if !ok {
		_ = c.codec.WriteError(f.ID, proto.NewError(proto.ErrCodeUnknownTool, "tool "+inv.Tool+" is not registered", nil))
		return
	}
	inv.Risk = capEntry.Risk

	// Permission proxy: policy decides; "ask" routes back to Butler.
	decision, err := s.proxy.Check(ctx, inv, capEntry.Source)
	if err != nil {
		_ = c.codec.WriteError(f.ID, proto.NewError(proto.ErrCodeInternal, "approval error: "+err.Error(), nil))
		return
	}
	if !decision.Allowed {
		_ = c.codec.WriteError(f.ID, proto.NewError(proto.ErrCodeDenied, "denied: "+decision.Reason, nil))
		return
	}

	call, err := s.south.Invoke(ctx, inv)
	if err != nil {
		pe, ok := err.(*proto.ProtoError)
		if !ok {
			pe = proto.NewError(proto.ErrCodeUpstream, err.Error(), nil)
		}
		_ = c.codec.WriteError(f.ID, pe)
		return
	}

	// Stream partial results as they arrive.
	for chunk := range call.Chunks() {
		cf, err := proto.NewFrame(f.ID, proto.TypeToolChunk, chunk)
		if err != nil {
			continue
		}
		cf.Stream = true
		if err := c.codec.WriteFrame(cf); err != nil {
			s.south.Cancel(call.ID, "north consumer gone")
			return
		}
	}

	// Terminal frame: result or error.
	res, err := call.Result(ctx)
	if err != nil {
		if pe, ok := err.(*proto.ProtoError); ok {
			_ = c.codec.WriteError(f.ID, pe)
		} else {
			_ = c.codec.WriteError(f.ID, proto.NewError(proto.ErrCodeInternal, err.Error(), nil))
		}
		return
	}
	rf, err := proto.NewFrame(f.ID, proto.TypeToolResult, res)
	if err != nil {
		_ = c.codec.WriteError(f.ID, proto.NewError(proto.ErrCodeInternal, "marshal result: "+err.Error(), nil))
		return
	}
	rf.Done = true
	_ = c.codec.WriteFrame(rf)
}

// ---- approval routing ----

// askOrigin implements approval.AskFunc: route the question to the Butler
// connection that triggered the invocation and wait for approve.answer.
func (s *Server) askOrigin(ctx context.Context, req proto.ApprovalRequest) (proto.ApprovalDecision, error) {
	ch := make(chan proto.ApprovalDecision, 1)
	s.mu.Lock()
	s.askWait[req.RequestID] = ch
	s.mu.Unlock()
	defer func() {
		s.mu.Lock()
		delete(s.askWait, req.RequestID)
		s.mu.Unlock()
	}()

	frame, err := proto.NewFrame(req.RequestID, proto.TypeApproveAsk, req)
	if err != nil {
		return proto.ApprovalDecision{}, err
	}
	s.broadcast(frame) // any Butler console may answer

	select {
	case d := <-ch:
		return d, nil
	case <-time.After(s.AskTimeout):
		return proto.ApprovalDecision{RequestID: req.RequestID, Allowed: false, Reason: "approval timed out"}, nil
	case <-ctx.Done():
		return proto.ApprovalDecision{}, ctx.Err()
	}
}

// deliverAnswer routes an approve.answer either to a pending local ask or to
// the south side (decision for a plugin-originated request).
func (s *Server) deliverAnswer(c *conn, d proto.ApprovalDecision) {
	s.mu.Lock()
	ch, local := s.askWait[d.RequestID]
	if local {
		delete(s.askWait, d.RequestID)
	}
	s.mu.Unlock()
	if local {
		ch <- d
		return
	}
	if err := s.south.AnswerApproval(d); err != nil {
		c.log.Warn("forward approval failed", "err", err)
	}
}

// ---- event broadcast ----

func (s *Server) broadcastEvents(ctx context.Context) {
	sub := s.pump.Subscribe(ctx)
	for ev := range sub {
		frame, err := proto.NewFrame("event-broadcast", proto.TypeEventPush, ev)
		if err != nil {
			continue
		}
		s.broadcast(frame)
	}
}

func (s *Server) broadcast(f *proto.Frame) {
	s.mu.Lock()
	conns := make([]*conn, 0, len(s.conns))
	for c := range s.conns {
		conns = append(conns, c)
	}
	s.mu.Unlock()
	for _, c := range conns {
		if err := c.codec.WriteFrame(f); err != nil {
			s.log.Debug("broadcast failed", "err", err)
			c.close()
		}
	}
}
