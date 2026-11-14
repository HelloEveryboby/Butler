// Command butler-dsh-connector is the channel connector between Butler
// (Python orchestrator) and the DSH host (Node plugin runtime).
//
// North: framed JSON-RPC over a Unix socket / Windows named pipe (Butler).
// South: framed JSON-RPC over the DSH host child process stdio.
//
// The connector owns capability synchronization, tool-call routing with
// streaming, the permission proxy, and child-process supervision. It holds
// no business logic of its own.
package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/HelloEveryboby/Butler/connector/internal/approval"
	"github.com/HelloEveryboby/Butler/connector/internal/config"
	"github.com/HelloEveryboby/Butler/connector/internal/events"
	"github.com/HelloEveryboby/Butler/connector/internal/north"
	"github.com/HelloEveryboby/Butler/connector/internal/proto"
	"github.com/HelloEveryboby/Butler/connector/internal/registry"
	"github.com/HelloEveryboby/Butler/connector/internal/south"
	"github.com/HelloEveryboby/Butler/connector/internal/transport"
)

// version is stamped at build time via -ldflags "-X main.version=...".
var version = "dev"

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "butler-dsh-connector:", err)
		os.Exit(1)
	}
}

func run() error {
	var (
		configPath  = flag.String("config", "", "path to connector config (JSON)")
		northAddr   = flag.String("north-addr", "", "override north listen address")
		showVersion = flag.Bool("version", false, "print version and exit")
	)
	flag.Parse()

	if *showVersion {
		fmt.Println("butler-dsh-connector", version)
		return nil
	}

	cfg, err := config.Load(*configPath)
	if err != nil {
		return err
	}
	if *northAddr != "" {
		cfg.North.Addr = *northAddr
	}
	log := newLogger(cfg)

	log.Info("starting", "version", version)

	// South side: DSH host child process + call multiplexer.
	reg := registry.New()
	pump := events.New(events.DefaultBuffer)
	defer pump.Close()

	// northServer is captured by the south hooks; declared before wiring.
	var northServer *north.Server

	southClient := south.New(south.Config{
		NodeCommand:   cfg.South.NodeCommand,
		NodeArgs:      cfg.South.NodeArgs,
		Env:           cfg.South.Env,
		Dir:           cfg.South.Dir,
		DefaultTimeout: cfg.SouthTimeout(),
	}, south.Hooks{
		OnRegistry: func(snap proto.RegistrySync) {
			if _, err := reg.Replace(snap.Capabilities); err != nil {
				log.Warn("registry replace failed", "err", err)
				return
			}
			log.Info("registry synced", "version", reg.Version(), "tools", reg.Len())
			northServer.BroadcastRegistry()
		},
		OnRegistryDiff: func(diff proto.RegistryDiff) {
			if _, err := reg.Upsert(diff.Upserts...); err != nil {
				log.Warn("registry diff apply failed", "err", err)
			}
			reg.Remove(diff.Removals...)
			northServer.BroadcastRegistry()
		},
		OnEvent: func(ev proto.Event) {
			pump.Publish(ev)
		},
		OnApprove: func(req proto.ApprovalRequest) {
			// Plugin-originated approval requests are forwarded north by the
			// north server's broadcast; answer routing is by request id.
			log.Info("plugin approval requested", "tool", req.Tool, "risk", req.Risk)
			approvals <- req
		},
	}, log)

	// North side: Butler-facing listener.
	addr := cfg.North.Addr
	if addr == "" {
		addr = transport.DefaultAddr()
	}
	ln, err := transport.Listen(addr)
	if err != nil {
		return err
	}
	log.Info("listening", "addr", addr)

	audit, err := approval.NewAuditLog(cfg.Approval.AuditLog, cfg.Approval.AuditMaxBytes)
	if err != nil {
		return err
	}
	defer audit.Close()

	northServer = north.New(ln, reg, pump, southClient, log, cfg.AskTimeout())
	northServer.SetProxy(approval.NewProxy(
		approval.Compile(cfg.Approval.Policy),
		northServer.Ask,
		audit,
		cfg.AskTimeout(),
	))

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if err := southClient.Start(ctx); err != nil {
		return err
	}
	defer southClient.Close()

	// Forward plugin-originated approval requests to Butler consoles.
	go func() {
		for req := range approvals {
			frame, err := proto.NewFrame(req.RequestID, proto.TypeApproveAsk, req)
			if err == nil {
				northServer.Broadcast(frame)
			}
		}
	}()

	return northServer.Serve(ctx)
}

// approvals carries plugin-originated approval requests toward north.
var approvals = make(chan proto.ApprovalRequest, 64)

func newLogger(cfg config.Config) *slog.Logger {
	opts := &slog.HandlerOptions{Level: parseLevel(cfg.Log.Level)}
	var handler slog.Handler
	if cfg.Log.Format == "json" {
		handler = slog.NewJSONHandler(os.Stderr, opts)
	} else {
		handler = slog.NewTextHandler(os.Stderr, opts)
	}
	return slog.New(handler)
}

func parseLevel(s string) slog.Level {
	switch s {
	case "debug":
		return slog.LevelDebug
	case "warn":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}
