package proto

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"os"
	"path/filepath"
	"testing"
)

var update = flag.Bool("update", false, "rewrite golden files")

// stream pairs two buffers into a minimal ReadWriteCloser for codec tests.
type stream struct {
	*bytes.Buffer
}

func (s stream) Close() error { return nil }

func newTestStream() *stream {
	return &stream{&bytes.Buffer{}}
}

func TestCodecRoundTrip(t *testing.T) {
	s := newTestStream()
	w := NewCodec(s)
	r := NewCodec(s)

	in, err := NewFrame("call-1", TypeToolInvoke, ToolInvoke{
		Tool: "doc-reader",
		Args: json.RawMessage(`{"path":"report.pdf"}`),
		Risk: RiskReadOnly,
	})
	if err != nil {
		t.Fatalf("NewFrame: %v", err)
	}
	if err := w.WriteFrame(in); err != nil {
		t.Fatalf("WriteFrame: %v", err)
	}
	out, err := r.ReadFrame()
	if err != nil {
		t.Fatalf("ReadFrame: %v", err)
	}
	if out.ID != in.ID || out.Type != in.Type || out.Version != ProtocolVersion {
		t.Fatalf("frame mismatch: got %+v want %+v", out, in)
	}
	var inv ToolInvoke
	if err := out.DecodePayload(&inv); err != nil {
		t.Fatalf("DecodePayload: %v", err)
	}
	if inv.Tool != "doc-reader" || inv.Risk != RiskReadOnly {
		t.Fatalf("payload mismatch: %+v", inv)
	}
}

func TestCodecRejectsOversizedFrame(t *testing.T) {
	s := newTestStream()
	// Craft a header claiming a frame above the limit.
	_, _ = s.Write([]byte{0xFF, 0xFF, 0xFF, 0xFF})
	r := NewCodec(s)
	_, err := r.ReadFrame()
	var pe *ProtoError
	if !errors.As(err, &pe) || pe.Code != ErrCodeMalformed {
		t.Fatalf("want malformed_frame error, got %v", err)
	}
}

func TestCodecRejectsMalformedBody(t *testing.T) {
	s := newTestStream()
	// Length 5, body "xxxxx" is not JSON.
	_, _ = s.Write([]byte{0, 0, 0, 5})
	_, _ = s.Write([]byte("xxxxx"))
	r := NewCodec(s)
	_, err := r.ReadFrame()
	var pe *ProtoError
	if !errors.As(err, &pe) || pe.Code != ErrCodeMalformed {
		t.Fatalf("want malformed_frame error, got %v", err)
	}
}

func TestCodecRejectsVersionMismatch(t *testing.T) {
	s := newTestStream()
	body := []byte(`{"v":99,"id":"x","type":"health.ping","ts":1}`)
	header := []byte{0, 0, 0, byte(len(body))}
	_, _ = s.Write(header)
	_, _ = s.Write(body)
	r := NewCodec(s)
	_, err := r.ReadFrame()
	var pe *ProtoError
	if !errors.As(err, &pe) || pe.Code != ErrCodeUnsupported {
		t.Fatalf("want unsupported error, got %v", err)
	}
}

// TestCodecGolden pins the exact wire representation of a frame. Control
// frames are replayed from Session Logs in production; byte stability is a
// protocol invariant, not an implementation detail.
func TestCodecGolden(t *testing.T) {
	in, err := NewFrame("call-42", TypeToolInvoke, ToolInvoke{
		Tool:      "greet",
		Args:      json.RawMessage(`{"name":"张三"}`),
		Risk:      RiskReadOnly,
		TimeoutMs: 5000,
	})
	if err != nil {
		t.Fatalf("NewFrame: %v", err)
	}
	in.TS = 1763124960000 // fixed timestamp for determinism

	body, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	golden := filepath.Join("testdata", "golden_tool_invoke.json")
	if *update {
		if err := os.MkdirAll("testdata", 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(golden, body, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	want, err := os.ReadFile(golden)
	if err != nil {
		t.Fatalf("read golden: %v (run: go test -update)", err)
	}
	if !bytes.Equal(bytes.TrimSpace(body), bytes.TrimSpace(want)) {
		t.Fatalf("wire format changed:\n got: %s\nwant: %s", body, want)
	}
}

func TestFrameTerminal(t *testing.T) {
	res, _ := NewFrame("x", TypeToolResult, ToolResult{Tool: "t"})
	if !res.IsTerminal() {
		t.Fatal("tool.result must be terminal")
	}
	chunk, _ := NewFrame("x", TypeToolChunk, ToolChunk{Seq: 1})
	if chunk.IsTerminal() {
		t.Fatal("tool.chunk must not be terminal")
	}
}

func TestCapabilityValidate(t *testing.T) {
	cases := []struct {
		name    string
		cap     Capability
		wantErr bool
	}{
		{"ok", Capability{Name: "t", Description: "d", Risk: RiskReadOnly}, false},
		{"no name", Capability{Description: "d", Risk: RiskReadOnly}, true},
		{"no description", Capability{Name: "t", Risk: RiskReadOnly}, true},
		{"bad risk", Capability{Name: "t", Description: "d", Risk: "danger"}, true},
		{"bad schema", Capability{Name: "t", Description: "d", Risk: RiskWrite, Schema: json.RawMessage(`{`)}, true},
	}
	for _, tc := range cases {
		c := tc.cap
		err := c.Validate()
		if (err != nil) != tc.wantErr {
			t.Errorf("%s: Validate() = %v, wantErr=%v", tc.name, err, tc.wantErr)
		}
	}
}

func TestTLVRoundTrip(t *testing.T) {
	var buf bytes.Buffer
	in := TLV{Tag: TagAudioPCM, Value: []byte{0xDE, 0xAD, 0xBE, 0xEF}}
	if err := WriteTLV(&buf, in); err != nil {
		t.Fatalf("WriteTLV: %v", err)
	}
	out, err := ReadTLV(&buf)
	if err != nil {
		t.Fatalf("ReadTLV: %v", err)
	}
	if out.Tag != in.Tag || !bytes.Equal(out.Value, in.Value) {
		t.Fatalf("TLV mismatch: got %+v want %+v", out, in)
	}
}

func TestTLVRejectsOversizedValue(t *testing.T) {
	big := TLV{Tag: TagDocBlob, Value: make([]byte, MaxTLVValue+1)}
	if _, err := big.MarshalBinary(); err == nil {
		t.Fatal("expected oversize error")
	}
}
