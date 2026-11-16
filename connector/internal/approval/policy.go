// Package approval implements the connector's permission proxy: every tool
// invocation is classified by blast radius and checked against an ordered
// rule set before it is forwarded south. Dangerous operations are default-deny
// on ambiguity — a request that cannot be classified is never silently
// allowed.
package approval

import (
	"fmt"
	"path"
	"strings"

	"github.com/HelloEveryboby/Butler/connector/internal/proto"
)

// Action is the verdict for a matching rule.
type Action string

const (
	ActionAllow Action = "allow"
	ActionDeny  Action = "deny"
	ActionAsk   Action = "ask" // defer to the human/Butler approval flow
)

// Rule matches tool invocations. The first matching rule in the ordered rule
// set wins. Empty fields match everything on that dimension.
type Rule struct {
	Tool    string          `json:"tool,omitempty"`    // glob on tool name, e.g. "fs.*"
	Source  string          `json:"source,omitempty"`  // plugin id glob
	Risk    proto.RiskClass `json:"risk,omitempty"`    // exact risk class
	Action  Action          `json:"action"`
	Reason  string          `json:"reason,omitempty"`
}

// Config is the serializable policy definition (loaded from the connector
// config file or embedded defaults).
type Config struct {
	Rules []Rule `json:"rules,omitempty"`
	// Defaults maps risk classes to actions for invocations that match no
	// explicit rule. Missing classes fall back to built-in safe defaults:
	// read_only -> allow, everything else -> ask.
	Defaults map[proto.RiskClass]Action `json:"defaults,omitempty"`
	// AllowedSources, when non-empty, is a whitelist of plugin ids. Tools
	// from other sources are denied outright.
	AllowedSources []string `json:"allowedSources,omitempty"`
}

// Policy is the compiled, immutable rule engine.
type Policy struct {
	rules          []Rule
	defaults       map[proto.RiskClass]Action
	allowedSources []string
}

// Default returns the built-in safe policy.
func Default() *Policy {
	return Compile(Config{})
}

// Compile validates and freezes a configuration into a Policy.
func Compile(cfg Config) *Policy {
	p := &Policy{
		defaults: map[proto.RiskClass]Action{
			proto.RiskReadOnly: ActionAllow,
			proto.RiskWrite:    ActionAsk,
			proto.RiskExecute:  ActionAsk,
			proto.RiskNetwork:  ActionAsk,
			proto.RiskUnknown:  ActionAsk,
		},
		allowedSources: append([]string(nil), cfg.AllowedSources...),
	}
	for cls, a := range cfg.Defaults {
		if a == ActionAllow || a == ActionDeny || a == ActionAsk {
			p.defaults[cls] = a
		}
	}
	for _, r := range cfg.Rules {
		if r.Action != ActionAllow && r.Action != ActionDeny && r.Action != ActionAsk {
			continue // skip invalid rules rather than fail closed at runtime
		}
		p.rules = append(p.rules, r)
	}
	return p
}

// Decision is the outcome of a policy evaluation.
type Decision struct {
	Action Action
	Reason string
}

// Decide evaluates the ordered rules, then the risk defaults. Unlisted or
// invalid risk classes resolve to ActionAsk (the safe choice), never allow.
func (p *Policy) Decide(tool, source string, risk proto.RiskClass) Decision {
	if !p.sourceAllowed(source) {
		return Decision{ActionDeny, fmt.Sprintf("source %q not in allowlist", source)}
	}
	for _, r := range p.rules {
		if r.matches(tool, source, risk) {
			return Decision{r.Action, r.Reason}
		}
	}
	if a, ok := p.defaults[risk]; ok {
		return Decision{a, "risk default"}
	}
	return Decision{ActionAsk, "unclassified risk"}
}

func (p *Policy) sourceAllowed(source string) bool {
	if len(p.allowedSources) == 0 {
		return true
	}
	for _, s := range p.allowedSources {
		if s == source {
			return true
		}
	}
	return false
}

func (r Rule) matches(tool, source string, risk proto.RiskClass) bool {
	if r.Tool != "" && !globMatch(r.Tool, tool) {
		return false
	}
	if r.Source != "" && !globMatch(r.Source, source) {
		return false
	}
	if r.Risk != "" && r.Risk != risk {
		return false
	}
	return true
}

// globMatch performs shell-style matching where "*" also crosses "." so that
// patterns like "fs.*" naturally cover "fs.read".
func globMatch(pattern, value string) bool {
	if ok, err := path.Match(pattern, value); err == nil && ok {
		return true
	}
	// Fallback: prefix glob semantics ("fs.*" matches "fs.a.b").
	if strings.HasSuffix(pattern, ".*") {
		return strings.HasPrefix(value, strings.TrimSuffix(pattern, "*"))
	}
	return false
}
