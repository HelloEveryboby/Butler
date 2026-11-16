// Package config loads and validates connector configuration. Precedence:
// built-in defaults < config file (JSON) < environment variables < flags
// (applied by the caller). Secrets are referenced by environment variable
// name only — the file must never contain credentials.
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/HelloEveryboby/Butler/connector/internal/approval"
)

// Config is the full connector configuration.
type Config struct {
	North    NorthConfig    `json:"north"`
	South    SouthConfig    `json:"south"`
	Approval ApprovalConfig `json:"approval"`
	Log      LogConfig      `json:"log"`
}

// NorthConfig configures the Butler-facing listener.
type NorthConfig struct {
	// Addr is a socket path (Unix) or named pipe path (Windows).
	// Empty means transport.DefaultAddr().
	Addr string `json:"addr"`
}

// SouthConfig configures the DSH host child process.
type SouthConfig struct {
	NodeCommand string   `json:"nodeCommand"` // e.g. "node"
	NodeArgs    []string `json:"nodeArgs"`    // e.g. ["lib_external/dsh-host/server.js"]
	Dir         string   `json:"dir"`         // working directory
	Env         []string `json:"env"`         // KEY=VALUE entries; ${VAR} refs are expanded
	// DefaultTimeoutMs bounds tool calls without a per-call timeout.
	DefaultTimeoutMs int64 `json:"defaultTimeoutMs"`
}

// ApprovalConfig configures the permission proxy.
type ApprovalConfig struct {
	AskTimeoutMs  int64          `json:"askTimeoutMs"`
	AuditLog      string         `json:"auditLog"`
	AuditMaxBytes int64          `json:"auditMaxBytes"`
	Policy        approval.Config `json:"policy"`
}

// LogConfig configures diagnostics.
type LogConfig struct {
	Level  string `json:"level"`  // debug|info|warn|error
	Format string `json:"format"` // json|text
}

// Default returns the built-in configuration.
func Default() Config {
	return Config{
		North: NorthConfig{},
		South: SouthConfig{
			NodeCommand:      "node",
			NodeArgs:         []string{"lib_external/dsh-host/server.js"},
			DefaultTimeoutMs: 120_000,
		},
		Approval: ApprovalConfig{
			AskTimeoutMs:  30_000,
			AuditLog:      "logs/connector-audit.jsonl",
			AuditMaxBytes: 16 << 20,
		},
		Log: LogConfig{Level: "info", Format: "text"},
	}
}

// Load reads a JSON config file (optional: path may be empty), merges it over
// defaults, applies environment overrides, and validates the result.
func Load(path string) (Config, error) {
	cfg := Default()
	if path != "" {
		raw, err := os.ReadFile(path)
		if err != nil {
			return cfg, fmt.Errorf("config: read %s: %w", path, err)
		}
		dec := json.NewDecoder(strings.NewReader(string(raw)))
		dec.DisallowUnknownFields()
		if err := dec.Decode(&cfg); err != nil {
			return cfg, fmt.Errorf("config: parse %s: %w", path, err)
		}
	}
	cfg.applyEnv()
	if err := cfg.Validate(); err != nil {
		return cfg, err
	}
	return cfg, nil
}

// applyEnv overlays BUTLER_DSH_* environment variables.
func (c *Config) applyEnv() {
	if v := os.Getenv("BUTLER_DSH_NORTH_ADDR"); v != "" {
		c.North.Addr = v
	}
	if v := os.Getenv("BUTLER_DSH_SOUTH_CMD"); v != "" {
		c.South.NodeCommand = v
	}
	if v := os.Getenv("BUTLER_DSH_LOG_LEVEL"); v != "" {
		c.Log.Level = v
	}
	// Expand ${VAR} references in child env entries.
	for i, e := range c.South.Env {
		c.South.Env[i] = expandEnv(e)
	}
}

// expandEnv resolves ${VAR} (only) inside KEY=VALUE entries, keeping any
// literal $ that is not part of a ${...} reference intact.
func expandEnv(entry string) string {
	k, v, ok := strings.Cut(entry, "=")
	if !ok {
		return entry
	}
	var b strings.Builder
	for i := 0; i < len(v); i++ {
		if v[i] == '$' && i+1 < len(v) && v[i+1] == '{' {
			if end := strings.IndexByte(v[i+2:], '}'); end >= 0 {
				name := v[i+2 : i+2+end]
				b.WriteString(os.Getenv(name))
				i += 2 + end
				continue
			}
		}
		b.WriteByte(v[i])
	}
	return k + "=" + b.String()
}

// Validate checks invariants that would otherwise fail deep at runtime.
func (c Config) Validate() error {
	if c.South.NodeCommand == "" {
		return fmt.Errorf("config: south.nodeCommand is required")
	}
	switch strings.ToLower(c.Log.Format) {
	case "json", "text":
	default:
		return fmt.Errorf("config: log.format must be json or text, got %q", c.Log.Format)
	}
	switch strings.ToLower(c.Log.Level) {
	case "debug", "info", "warn", "error":
	default:
		return fmt.Errorf("config: log.level must be debug|info|warn|error, got %q", c.Log.Level)
	}
	return nil
}

// SouthTimeout returns the default tool-call timeout as a duration.
func (c Config) SouthTimeout() time.Duration {
	return time.Duration(c.South.DefaultTimeoutMs) * time.Millisecond
}

// AskTimeout returns the interactive approval timeout as a duration.
func (c Config) AskTimeout() time.Duration {
	return time.Duration(c.Approval.AskTimeoutMs) * time.Millisecond
}
