//go:build !windows

package transport

import (
	"context"
	"fmt"
	"net"
	"os"
	"path/filepath"
)

// platformDefaultAddr returns a per-user socket path.
func platformDefaultAddr() string {
	dir := os.Getenv("XDG_RUNTIME_DIR")
	if dir == "" {
		dir = os.TempDir()
	}
	return filepath.Join(dir, "butler-dsh-connector.sock")
}

// Listen opens a Unix domain socket at addr, cleaning up a stale socket file
// left by an unclean shutdown.
func Listen(addr string) (Listener, error) {
	if err := os.MkdirAll(filepath.Dir(addr), 0o750); err != nil {
		return nil, fmt.Errorf("transport: create socket dir: %w", err)
	}
	// Probe whether a live connector already owns the socket: connecting
	// successfully means "in use", failing means "stale, safe to remove".
	if conn, err := net.Dial("unix", addr); err == nil {
		conn.Close()
		return nil, fmt.Errorf("transport: socket %s is already in use", addr)
	}
	if err := os.Remove(addr); err != nil && !os.IsNotExist(err) {
		return nil, fmt.Errorf("transport: remove stale socket: %w", err)
	}
	ln, err := net.Listen("unix", addr)
	if err != nil {
		return nil, fmt.Errorf("transport: listen on %s: %w", addr, err)
	}
	// Restrict to the owning user.
	if err := os.Chmod(addr, 0o600); err != nil {
		ln.Close()
		return nil, fmt.Errorf("transport: chmod socket: %w", err)
	}
	return ln, nil
}

type unixDialer struct{ addr string }

// Dial connects to the Unix socket.
func (d unixDialer) Dial(ctx context.Context) (net.Conn, error) {
	var nd net.Dialer
	return nd.DialContext(ctx, "unix", d.addr)
}

// NewDialer returns a Dialer for the platform address.
func NewDialer(addr string) Dialer { return unixDialer{addr: addr} }
