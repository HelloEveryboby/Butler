package proto

import (
	"bufio"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"sync"
	"time"
)

// Codec performs length-prefixed framed I/O over a reliable byte stream.
// Reads and writes are safe to use from different goroutines; writes are
// serialized internally so frames never interleave on the wire.
type Codec struct {
	r   *bufio.Reader
	w   *bufio.Writer
	wmu sync.Mutex
	// closeOnce guards the underlying stream shutdown.
	closeOnce sync.Once
	closer    io.Closer
}

// NewCodec wraps a bidirectional byte stream (net.Conn, pipe pair, ...).
func NewCodec(stream io.ReadWriteCloser) *Codec {
	return &Codec{
		r:      bufio.NewReaderSize(stream, 64<<10),
		w:      bufio.NewWriterSize(stream, 64<<10),
		closer: stream,
	}
}

// ReadFrame blocks until one complete frame arrives or the stream fails.
// The returned frame is validated: version and size invariants are enforced.
func (c *Codec) ReadFrame() (*Frame, error) {
	var hdr [4]byte
	if _, err := io.ReadFull(c.r, hdr[:]); err != nil {
		return nil, err
	}
	n := binary.BigEndian.Uint32(hdr[:])
	if n == 0 {
		return nil, NewError(ErrCodeMalformed, "zero-length frame", nil)
	}
	if n > MaxFrameSize {
		return nil, NewError(ErrCodeMalformed,
			fmt.Sprintf("frame of %d bytes exceeds limit %d", n, MaxFrameSize), nil)
	}
	buf := make([]byte, n)
	if _, err := io.ReadFull(c.r, buf); err != nil {
		return nil, fmt.Errorf("proto: truncated frame body: %w", err)
	}
	var f Frame
	if err := json.Unmarshal(buf, &f); err != nil {
		return nil, NewError(ErrCodeMalformed, "frame body is not valid JSON", nil)
	}
	if f.Version != ProtocolVersion {
		return nil, NewError(ErrCodeUnsupported,
			fmt.Sprintf("protocol version %d, want %d", f.Version, ProtocolVersion), nil)
	}
	if f.Type == "" || f.ID == "" {
		return nil, NewError(ErrCodeMalformed, "frame missing id or type", nil)
	}
	return &f, nil
}

// WriteFrame serializes and flushes one frame atomically.
func (c *Codec) WriteFrame(f *Frame) error {
	if f == nil {
		return fmt.Errorf("proto: write nil frame")
	}
	f.Version = ProtocolVersion
	if f.TS == 0 {
		f.TS = time.Now().UnixMilli()
	}
	body, err := json.Marshal(f)
	if err != nil {
		return fmt.Errorf("proto: marshal frame: %w", err)
	}
	if len(body) > MaxFrameSize {
		return NewError(ErrCodeMalformed,
			fmt.Sprintf("encoded frame of %d bytes exceeds limit %d", len(body), MaxFrameSize), nil)
	}

	c.wmu.Lock()
	defer c.wmu.Unlock()
	var hdr [4]byte
	binary.BigEndian.PutUint32(hdr[:], uint32(len(body)))
	if _, err := c.w.Write(hdr[:]); err != nil {
		return fmt.Errorf("proto: write header: %w", err)
	}
	if _, err := c.w.Write(body); err != nil {
		return fmt.Errorf("proto: write body: %w", err)
	}
	if err := c.w.Flush(); err != nil {
		return fmt.Errorf("proto: flush: %w", err)
	}
	return nil
}

// WriteError is a convenience for emitting a terminal error frame.
func (c *Codec) WriteError(id string, pe *ProtoError) error {
	f := &Frame{
		Version: ProtocolVersion,
		ID:      id,
		Type:    TypeError,
		Done:    true,
		Error:   pe,
		TS:      time.Now().UnixMilli(),
	}
	return c.WriteFrame(f)
}

// Close shuts the underlying stream exactly once.
func (c *Codec) Close() error {
	var err error
	c.closeOnce.Do(func() {
		if c.closer != nil {
			err = c.closer.Close()
		}
	})
	return err
}
