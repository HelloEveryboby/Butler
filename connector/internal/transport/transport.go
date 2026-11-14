// Package transport abstracts the north-side byte channel. On Unix the
// connector listens on a filesystem socket; on Windows it listens on a named
// pipe. Both hand back plain net.Conn values so the rest of the connector is
// platform-agnostic.
package transport

import (
	"context"
	"net"
)

// Listener accepts north-side connections from Butler.
type Listener interface {
	Accept() (net.Conn, error)
	Close() error
	Addr() net.Addr
}

// Dialer opens north-side connections (used by Butler-side clients and tests).
type Dialer interface {
	Dial(ctx context.Context) (net.Conn, error)
}

// DefaultAddr returns the platform-conventional default address.
// Unix: a socket path under the runtime dir; Windows: a named pipe path.
func DefaultAddr() string { return platformDefaultAddr() }
