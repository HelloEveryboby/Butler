package approval

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/HelloEveryboby/Butler/connector/internal/proto"
)

// AskFunc bridges to the north side (Butler's approval UI / operator). It
// must return a decision or an error; on error or timeout the proxy falls
// back to deny for dangerous invocations.
type AskFunc func(ctx context.Context, req proto.ApprovalRequest) (proto.ApprovalDecision, error)

// Proxy turns policy decisions into enforced outcomes, consulting the human
// approval flow when required and writing an append-only audit trail.
type Proxy struct {
	policy   *Policy
	ask      AskFunc
	audit    *AuditLog
	timeout  time.Duration

	mu        sync.Mutex
	remembered map[string]Decision // "source/tool" -> cached verdict
}

// NewProxy wires a Proxy. ask may be nil when no interactive channel exists;
// in that case ActionAsk degrades to deny (fail-closed).
func NewProxy(policy *Policy, ask AskFunc, audit *AuditLog, timeout time.Duration) *Proxy {
	if timeout <= 0 {
		timeout = 30 * time.Second
	}
	return &Proxy{
		policy:    policy,
		ask:       ask,
		audit:     audit,
		timeout:   timeout,
		remembered: make(map[string]Decision),
	}
}

// Check runs the full approval workflow for one invocation. A nil error with
// Allowed=true is the only green light to forward the call south.
func (p *Proxy) Check(ctx context.Context, inv proto.ToolInvoke, source string) (proto.ApprovalDecision, error) {
	req := proto.ApprovalRequest{
		RequestID: requestID(),
		Tool:      inv.Tool,
		Source:    source,
		Risk:      inv.Risk,
		Args:      inv.Args,
	}

	// 1. Cached decision (from a previous "remember" answer).
	key := source + "/" + inv.Tool
	p.mu.Lock()
	cached, hit := p.remembered[key]
	p.mu.Unlock()
	if hit {
		p.audit.write("cached", req, cached.Action, cached.Reason)
		return proto.ApprovalDecision{RequestID: req.RequestID, Allowed: cached.Action == ActionAllow, Reason: "cached: " + cached.Reason}, nil
	}

	// 2. Policy evaluation.
	dec := p.policy.Decide(inv.Tool, source, inv.Risk)
	switch dec.Action {
	case ActionAllow:
		p.audit.write("policy", req, ActionAllow, dec.Reason)
		return proto.ApprovalDecision{RequestID: req.RequestID, Allowed: true, Reason: dec.Reason}, nil
	case ActionDeny:
		p.audit.write("policy", req, ActionDeny, dec.Reason)
		return proto.ApprovalDecision{RequestID: req.RequestID, Allowed: false, Reason: dec.Reason}, nil
	}

	// 3. ActionAsk: interactive approval with timeout, fail-closed.
	if p.ask == nil {
		p.audit.write("no-approver", req, ActionDeny, "ask required but no approval channel configured")
		return proto.ApprovalDecision{RequestID: req.RequestID, Allowed: false, Reason: "no approval channel"}, nil
	}
	askCtx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()
	answer, err := p.ask(askCtx, req)
	if err != nil {
		p.audit.write("ask-error", req, ActionDeny, err.Error())
		return proto.ApprovalDecision{RequestID: req.RequestID, Allowed: false, Reason: "approval failed: " + err.Error()}, nil
	}

	final := ActionDeny
	if answer.Allowed {
		final = ActionAllow
	}
	p.audit.write("human", req, final, answer.Reason)
	if answer.Remember {
		p.mu.Lock()
		p.remembered[key] = Decision{final, answer.Reason}
		p.mu.Unlock()
	}
	return answer, nil
}

// ---- audit trail ----

// AuditEntry is one line in the append-only JSONL audit log.
type AuditEntry struct {
	TS       time.Time       `json:"ts"`
	Origin   string          `json:"origin"` // policy | human | cached | ask-error | no-approver
	Request  json.RawMessage `json:"request"`
	Action   Action          `json:"action"`
	Reason   string          `json:"reason,omitempty"`
}

// AuditLog is a size-rotated JSONL sink. All writes are serialized.
type AuditLog struct {
	mu       sync.Mutex
	path     string
	maxBytes int64
	file     *os.File
}

// NewAuditLog opens (creating if needed) an audit log at path. maxBytes <= 0
// disables rotation.
func NewAuditLog(path string, maxBytes int64) (*AuditLog, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
		return nil, fmt.Errorf("approval: create audit dir: %w", err)
	}
	a := &AuditLog{path: path, maxBytes: maxBytes}
	if err := a.open(); err != nil {
		return nil, err
	}
	return a, nil
}

func (a *AuditLog) open() error {
	f, err := os.OpenFile(a.path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o640)
	if err != nil {
		return fmt.Errorf("approval: open audit log: %w", err)
	}
	a.file = f
	return nil
}

// Close flushes and closes the log.
func (a *AuditLog) Close() error {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.file == nil {
		return nil
	}
	err := a.file.Close()
	a.file = nil
	return err
}

func (a *AuditLog) write(origin string, req proto.ApprovalRequest, action Action, reason string) {
	if a == nil {
		return // audit sink disabled
	}
	raw, _ := json.Marshal(req)
	e := AuditEntry{TS: time.Now().UTC(), Origin: origin, Request: raw, Action: action, Reason: reason}
	line, _ := json.Marshal(e)

	a.mu.Lock()
	defer a.mu.Unlock()
	if a.file == nil {
		return
	}
	if a.maxBytes > 0 {
		if st, err := a.file.Stat(); err == nil && st.Size()+int64(len(line)) > a.maxBytes {
			_ = a.file.Close()
			_ = os.Rename(a.path, a.path+".1") // keep exactly one generation
			if err := a.open(); err != nil {
				return
			}
		}
	}
	_, _ = a.file.Write(append(line, '\n'))
}

func requestID() string {
	return fmt.Sprintf("apr-%d", time.Now().UnixNano())
}
