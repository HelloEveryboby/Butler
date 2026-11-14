package south

import (
	"context"
	"encoding/json"
	"net"
	"testing"
	"time"

	"github.com/HelloEveryboby/Butler/connector/internal/proto"
)

// fakeSouth simulates the DSH host side of the wire on a net.Pipe.
type fakeSouth struct {
	codec *proto.Codec
}

func newFakeSouth(t *testing.T) (*fakeSouth, *Client) {
	t.Helper()
	local, remote := net.Pipe()
	fs := &fakeSouth{codec: proto.NewCodec(remote)}
	c := New(Config{DefaultTimeout: 2 * time.Second}, Hooks{}, nil)
	c.AttachStream(local)
	return fs, c
}

func TestInvokeStreamsChunksThenResult(t *testing.T) {
	fs, c := newFakeSouth(t)
	defer c.Close()

	go func() {
		f, err := fs.codec.ReadFrame()
		if err != nil {
			return
		}
		for i := 0; i < 3; i++ {
			chunk, _ := proto.NewFrame(f.ID, proto.TypeToolChunk, proto.ToolChunk{
				Seq:  uint32(i),
				Data: json.RawMessage(`{"partial":true}`),
			})
			_ = fs.codec.WriteFrame(chunk)
		}
		res, _ := proto.NewFrame(f.ID, proto.TypeToolResult, proto.ToolResult{
			Tool:    "doc-reader",
			Content: json.RawMessage(`{"text":"hello"}`),
		})
		_ = fs.codec.WriteFrame(res)
	}()

	call, err := c.Invoke(context.Background(), proto.ToolInvoke{Tool: "doc-reader"})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	var seqs []uint32
	for chunk := range call.Chunks() {
		seqs = append(seqs, chunk.Seq)
	}
	if len(seqs) != 3 {
		t.Fatalf("chunks = %v, want 3", seqs)
	}
	res, err := call.Result(context.Background())
	if err != nil {
		t.Fatalf("Result: %v", err)
	}
	if res.Tool != "doc-reader" {
		t.Fatalf("result = %+v", res)
	}
}

func TestInvokeTimeoutFailsCallAndCancels(t *testing.T) {
	fs, c := newFakeSouth(t)
	defer c.Close()

	// Read the invoke and the follow-up cancel; never answer.
	cancelSeen := make(chan string, 1)
	go func() {
		inv, err := fs.codec.ReadFrame()
		if err != nil {
			return
		}
		if cancel, err := fs.codec.ReadFrame(); err == nil && cancel.Type == proto.TypeToolCancel {
			cancelSeen <- inv.ID
		}
	}()

	call, err := c.Invoke(context.Background(), proto.ToolInvoke{Tool: "slow", TimeoutMs: 50})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	_, err = call.Result(context.Background())
	pe, ok := err.(*proto.ProtoError)
	if !ok || pe.Code != proto.ErrCodeTimeout {
		t.Fatalf("want timeout error, got %v", err)
	}
	select {
	case id := <-cancelSeen:
		if id != call.ID {
			t.Fatalf("cancel for %q, want %q", id, call.ID)
		}
	case <-time.After(time.Second):
		t.Fatal("tool.cancel was not sent south")
	}
}

func TestUpstreamErrorPropagates(t *testing.T) {
	fs, c := newFakeSouth(t)
	defer c.Close()

	go func() {
		f, err := fs.codec.ReadFrame()
		if err != nil {
			return
		}
		_ = fs.codec.WriteError(f.ID, proto.NewError(proto.ErrCodeUpstream, "plugin crashed", nil))
	}()

	call, err := c.Invoke(context.Background(), proto.ToolInvoke{Tool: "boom"})
	if err != nil {
		t.Fatalf("Invoke: %v", err)
	}
	_, err = call.Result(context.Background())
	pe, ok := err.(*proto.ProtoError)
	if !ok || pe.Code != proto.ErrCodeUpstream {
		t.Fatalf("want upstream error, got %v", err)
	}
}

func TestRegistrySyncSignalsReady(t *testing.T) {
	fs, c := newFakeSouth(t)
	defer c.Close()

	go func() {
		snap, _ := proto.NewFrame("sync-1", proto.TypeRegistrySync, proto.RegistrySync{
			Version:      1,
			Capabilities: []proto.Capability{{Name: "t", Description: "d", Risk: proto.RiskReadOnly}},
		})
		_ = fs.codec.WriteFrame(snap)
	}()

	select {
	case <-c.Ready():
	case <-time.After(time.Second):
		t.Fatal("ready not signalled after registry.sync")
	}
}

func TestInvokeWhenDisconnected(t *testing.T) {
	c := New(Config{}, Hooks{}, nil)
	_, err := c.Invoke(context.Background(), proto.ToolInvoke{Tool: "x"})
	pe, ok := err.(*proto.ProtoError)
	if !ok || pe.Code != proto.ErrCodeUnavailable {
		t.Fatalf("want unavailable error, got %v", err)
	}
}
