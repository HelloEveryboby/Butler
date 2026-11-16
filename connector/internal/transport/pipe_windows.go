//go:build windows

package transport

import (
	"context"
	"fmt"
	"net"

	"github.com/Microsoft/go-winio"
)

// platformDefaultAddr returns the conventional named-pipe path.
func platformDefaultAddr() string {
	return `\\.\pipe\butler-dsh-connector`
}

// Listen opens a named pipe restricted to the current user + administrators.
func Listen(addr string) (Listener, error) {
	cfg := &winio.PipeConfig{
		// Local user + Administrators + SYSTEM only.
		SecurityDescriptor: "D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;IU)",
		MessageMode:        false, // byte mode; framing is handled by proto.Codec
		InputBufferSize:    256 << 10,
		OutputBufferSize:   256 << 10,
	}
	ln, err := winio.ListenPipe(addr, cfg)
	if err != nil {
		return nil, fmt.Errorf("transport: listen on pipe %s: %w", addr, err)
	}
	return ln, nil
}

type pipeDialer struct{ addr string }

// Dial connects to the named pipe.
func (d pipeDialer) Dial(ctx context.Context) (net.Conn, error) {
	return winio.DialPipeContext(ctx, d.addr)
}

// NewDialer returns a Dialer for the platform address.
func NewDialer(addr string) Dialer { return pipeDialer{addr: addr} }
