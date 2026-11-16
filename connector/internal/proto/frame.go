// Package proto defines the butler-dsh-connector control-plane protocol.
//
// The protocol is a symmetric, length-prefixed JSON frame stream carried over
// a reliable byte channel (Unix socket / Windows named pipe / child-process
// stdio). Every frame is self-describing and correlated by ID, which allows
// multiplexing many in-flight tool calls over a single connection together
// with streaming chunk frames and out-of-band events.
//
// Design invariants:
//   - Frames are never larger than MaxFrameSize; large binary payloads travel
//     on the TLV data plane (see tlv.go) or as streamed chunks.
//   - The protocol version is negotiated at handshake time (registry.sync);
//     unknown frame types must be answered with ErrCodeUnsupported, never
//     dropped silently.
//   - Control frames are idempotent where possible so that replaying a
//     Session Log is safe.
package proto

import (
	"encoding/json"
	"fmt"
	"time"
)

// ProtocolVersion is the current wire version. Bump on breaking changes.
const ProtocolVersion = 1

// MaxFrameSize bounds a single control-plane frame (16 MiB).
const MaxFrameSize = 16 << 20

// FrameType identifies the semantic meaning of a frame.
type FrameType string

const (
	TypeToolInvoke    FrameType = "tool.invoke"     // north -> south: execute a tool
	TypeToolChunk     FrameType = "tool.chunk"      // south -> north: streamed partial result
	TypeToolResult    FrameType = "tool.result"     // south -> north: final result (terminal)
	TypeToolCancel    FrameType = "tool.cancel"     // north -> south: abort an in-flight call
	TypeEventPush     FrameType = "event.push"      // south -> north: session/plugin events
	TypeRegistrySync  FrameType = "registry.sync"   // bidirectional: full capability snapshot
	TypeRegistryDiff  FrameType = "registry.diff"   // south -> north: incremental capability delta
	TypeApproveAsk    FrameType = "approve.ask"     // south -> north: permission request
	TypeApproveAnswer FrameType = "approve.answer"  // north -> south: permission decision
	TypeHealthPing    FrameType = "health.ping"     // bidirectional: liveness probe
	TypeHealthPong    FrameType = "health.pong"     // bidirectional: liveness reply
	TypeError         FrameType = "error"           // terminal error for the referenced ID
)

// ErrorCode is a stable, machine-readable error classification.
type ErrorCode string

const (
	ErrCodeMalformed   ErrorCode = "malformed_frame"
	ErrCodeUnknownTool ErrorCode = "unknown_tool"
	ErrCodeTimeout     ErrorCode = "timeout"
	ErrCodeCancelled   ErrorCode = "cancelled"
	ErrCodeDenied      ErrorCode = "denied"
	ErrCodeUpstream    ErrorCode = "upstream_error"
	ErrCodeUnavailable ErrorCode = "unavailable"
	ErrCodeUnsupported ErrorCode = "unsupported"
	ErrCodeInternal    ErrorCode = "internal"
)

// ProtoError is the error payload carried by error frames.
type ProtoError struct {
	Code    ErrorCode       `json:"code"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data,omitempty"`
}

// Error implements the error interface.
func (e *ProtoError) Error() string {
	if e == nil {
		return "<nil>"
	}
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

// NewError builds a ProtoError with an optional structured data payload.
func NewError(code ErrorCode, msg string, data any) *ProtoError {
	pe := &ProtoError{Code: code, Message: msg}
	if data != nil {
		if raw, err := json.Marshal(data); err == nil {
			pe.Data = raw
		}
	}
	return pe
}

// Frame is the control-plane envelope. Payload is typed by Type.
type Frame struct {
	Version int             `json:"v"`
	ID      string          `json:"id"`
	Type    FrameType       `json:"type"`
	Stream  bool            `json:"stream,omitempty"`
	Done    bool            `json:"done,omitempty"`
	Payload json.RawMessage `json:"payload,omitempty"`
	Error   *ProtoError     `json:"error,omitempty"`
	TS      int64           `json:"ts"`
}

// NewFrame marshals payload (may be nil) into a frame of the given type.
func NewFrame(id string, t FrameType, payload any) (*Frame, error) {
	f := &Frame{
		Version: ProtocolVersion,
		ID:      id,
		Type:    t,
		TS:      time.Now().UnixMilli(),
	}
	if payload != nil {
		raw, err := json.Marshal(payload)
		if err != nil {
			return nil, fmt.Errorf("proto: marshal payload for %s: %w", t, err)
		}
		f.Payload = raw
	}
	return f, nil
}

// DecodePayload unmarshals the frame payload into v.
func (f *Frame) DecodePayload(v any) error {
	if len(f.Payload) == 0 {
		return fmt.Errorf("proto: frame %s has empty payload", f.Type)
	}
	if err := json.Unmarshal(f.Payload, v); err != nil {
		return fmt.Errorf("proto: decode payload of %s: %w", f.Type, err)
	}
	return nil
}

// IsTerminal reports whether the frame completes the call referenced by ID.
func (f *Frame) IsTerminal() bool {
	return f.Type == TypeToolResult || f.Type == TypeError
}

// ---- payload schemas ----

// RiskClass classifies the blast radius of a tool invocation. It drives the
// approval policy; the south side (DSH host shim) is responsible for tagging
// capabilities with a truthful risk class.
type RiskClass string

const (
	RiskReadOnly RiskClass = "read_only"
	RiskWrite    RiskClass = "write"
	RiskExecute  RiskClass = "execute"
	RiskNetwork  RiskClass = "network"
	RiskUnknown  RiskClass = "unknown"
)

// Valid reports whether the risk class is one of the known constants.
func (r RiskClass) Valid() bool {
	switch r {
	case RiskReadOnly, RiskWrite, RiskExecute, RiskNetwork, RiskUnknown:
		return true
	}
	return false
}

// ToolInvoke requests execution of a tool on the south side.
type ToolInvoke struct {
	Tool string          `json:"tool"`
	Args json.RawMessage `json:"args,omitempty"`
	Risk RiskClass       `json:"risk,omitempty"`
	// TimeoutMs caps the call; 0 means the connection default applies.
	TimeoutMs int64 `json:"timeoutMs,omitempty"`
}

// ToolChunk is one streamed fragment of a tool result.
type ToolChunk struct {
	Seq  uint32          `json:"seq"`
	Data json.RawMessage `json:"data"`
}

// ToolResult is the terminal result of a tool invocation.
type ToolResult struct {
	Tool    string          `json:"tool"`
	Content json.RawMessage `json:"content,omitempty"`
	IsError bool            `json:"isError,omitempty"`
}

// ToolCancel aborts an in-flight invocation.
type ToolCancel struct {
	Reason string `json:"reason,omitempty"`
}

// Event is a session/plugin event emitted by the south side and mirrored into
// Butler's event bus. Events are append-only facts; never mutate them.
type Event struct {
	Topic string          `json:"topic"`
	Data  json.RawMessage `json:"data,omitempty"`
	TS    int64           `json:"ts"`
}

// Capability describes one tool exported by the DSH plugin host.
type Capability struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	Schema      json.RawMessage `json:"schema,omitempty"` // JSON Schema of args
	Risk        RiskClass       `json:"risk"`
	Source      string          `json:"source"`  // plugin id that provides the tool
	SourceVer   string          `json:"sourceVer,omitempty"`
}

// Validate checks the structural invariants of a capability.
func (c *Capability) Validate() error {
	if c.Name == "" {
		return fmt.Errorf("proto: capability name is empty")
	}
	if c.Description == "" {
		return fmt.Errorf("proto: capability %q has empty description", c.Name)
	}
	if !c.Risk.Valid() {
		return fmt.Errorf("proto: capability %q has invalid risk class %q", c.Name, c.Risk)
	}
	if len(c.Schema) > 0 && !json.Valid(c.Schema) {
		return fmt.Errorf("proto: capability %q schema is not valid JSON", c.Name)
	}
	return nil
}

// RegistrySync is a full capability snapshot with a monotonic version.
type RegistrySync struct {
	Version   uint64       `json:"version"`
	Capabilities []Capability `json:"capabilities"`
}

// RegistryDiff is an incremental update. Receivers whose local version does
// not match From must request a full RegistrySync instead of applying it.
type RegistryDiff struct {
	From     uint64       `json:"from"`
	To       uint64       `json:"to"`
	Upserts  []Capability `json:"upserts,omitempty"`
	Removals []string     `json:"removals,omitempty"`
}

// ApprovalRequest asks the north side (Butler) for a permission decision.
type ApprovalRequest struct {
	RequestID string          `json:"requestId"`
	Tool      string          `json:"tool"`
	Source    string          `json:"source,omitempty"`
	Risk      RiskClass       `json:"risk"`
	Args      json.RawMessage `json:"args,omitempty"`
	Reason    string          `json:"reason,omitempty"`
}

// ApprovalDecision is the answer to an ApprovalRequest.
type ApprovalDecision struct {
	RequestID string `json:"requestId"`
	Allowed   bool   `json:"allowed"`
	Reason    string `json:"reason,omitempty"`
	// Remember asks the proxy to cache this decision for the tool+source pair.
	Remember bool `json:"remember,omitempty"`
}
