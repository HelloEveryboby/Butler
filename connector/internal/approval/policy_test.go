package approval

import (
	"testing"

	"github.com/HelloEveryboby/Butler/connector/internal/proto"
)

func TestDefaultPolicy(t *testing.T) {
	p := Default()
	cases := []struct {
		name string
		risk proto.RiskClass
		want Action
	}{
		{"read allowed", proto.RiskReadOnly, ActionAllow},
		{"write asks", proto.RiskWrite, ActionAsk},
		{"execute asks", proto.RiskExecute, ActionAsk},
		{"network asks", proto.RiskNetwork, ActionAsk},
		{"unknown asks", proto.RiskUnknown, ActionAsk},
	}
	for _, tc := range cases {
		d := p.Decide("tool", "plugin", tc.risk)
		if d.Action != tc.want {
			t.Errorf("%s: got %s, want %s", tc.name, d.Action, tc.want)
		}
	}
}

func TestUnlistedRiskFailsClosed(t *testing.T) {
	p := Default()
	d := p.Decide("tool", "plugin", proto.RiskClass("sketchy"))
	if d.Action != ActionAsk {
		t.Fatalf("unlisted risk must ask, got %s", d.Action)
	}
}

func TestOrderedRulesFirstMatchWins(t *testing.T) {
	p := Compile(Config{
		Rules: []Rule{
			{Tool: "fs.*", Risk: proto.RiskWrite, Action: ActionDeny, Reason: "writes locked down"},
			{Tool: "fs.export", Action: ActionAllow, Reason: "explicit export exception"},
		},
	})
	d := p.Decide("fs.write", "p", proto.RiskWrite)
	if d.Action != ActionDeny {
		t.Fatalf("first rule should win: got %s", d.Action)
	}
	d = p.Decide("fs.export", "p", proto.RiskReadOnly)
	if d.Action != ActionAllow {
		t.Fatalf("exception rule should allow: got %s", d.Action)
	}
}

func TestSourceAllowlist(t *testing.T) {
	p := Compile(Config{AllowedSources: []string{"trusted-plugin"}})
	if d := p.Decide("tool", "trusted-plugin", proto.RiskReadOnly); d.Action != ActionAllow {
		t.Fatalf("allowlisted source denied: %+v", d)
	}
	if d := p.Decide("tool", "evil-plugin", proto.RiskReadOnly); d.Action != ActionDeny {
		t.Fatalf("non-allowlisted source allowed: %+v", d)
	}
}

func TestCustomDefaults(t *testing.T) {
	p := Compile(Config{
		Defaults: map[proto.RiskClass]Action{
			proto.RiskNetwork: ActionDeny,
		},
	})
	if d := p.Decide("fetch", "p", proto.RiskNetwork); d.Action != ActionDeny {
		t.Fatalf("custom default not applied: %+v", d)
	}
	// Untouched classes keep built-in safe defaults.
	if d := p.Decide("read", "p", proto.RiskReadOnly); d.Action != ActionAllow {
		t.Fatalf("read default broken: %+v", d)
	}
}

func TestGlobMatching(t *testing.T) {
	cases := []struct {
		pattern, value string
		want           bool
	}{
		{"fs.*", "fs.read", true},
		{"fs.*", "fs.a.b", true},
		{"fs.*", "net.read", false},
		{"exact", "exact", true},
		{"*", "anything", true},
	}
	for _, tc := range cases {
		if got := globMatch(tc.pattern, tc.value); got != tc.want {
			t.Errorf("globMatch(%q,%q) = %v, want %v", tc.pattern, tc.value, got, tc.want)
		}
	}
}

func TestInvalidRuleActionSkipped(t *testing.T) {
	p := Compile(Config{
		Rules: []Rule{
			{Tool: "*", Action: "yolo"}, // invalid: must be ignored
			{Tool: "*", Action: ActionDeny},
		},
	})
	if d := p.Decide("t", "p", proto.RiskReadOnly); d.Action != ActionDeny {
		t.Fatalf("valid rule should apply: %+v", d)
	}
}
