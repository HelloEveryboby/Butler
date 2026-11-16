package events

import (
	"context"
	"testing"
	"time"

	"github.com/HelloEveryboby/Butler/connector/internal/proto"
)

func TestPublishDeliversToAllSubscribers(t *testing.T) {
	p := New(8)
	defer p.Close()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	a := p.Subscribe(ctx)
	b := p.Subscribe(ctx)
	p.Publish(proto.Event{Topic: "test"})

	for name, ch := range map[string]<-chan proto.Event{"a": a, "b": b} {
		select {
		case ev := <-ch:
			if ev.Topic != "test" {
				t.Fatalf("%s: got topic %q", name, ev.Topic)
			}
		case <-time.After(time.Second):
			t.Fatalf("%s: event not delivered", name)
		}
	}
}

func TestSlowSubscriberDropsOldest(t *testing.T) {
	p := New(2)
	defer p.Close()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sub := p.Subscribe(ctx)
	for i := 0; i < 5; i++ {
		p.Publish(proto.Event{Topic: "e"})
	}
	if p.Dropped() == 0 {
		t.Fatal("expected dropped events for slow consumer")
	}
	// The buffered channel must still hold the freshest events.
	if got := len(sub); got != 2 {
		t.Fatalf("buffer = %d, want 2", got)
	}
}

func TestUnsubscribeOnContextDone(t *testing.T) {
	p := New(8)
	defer p.Close()
	ctx, cancel := context.WithCancel(context.Background())
	p.Subscribe(ctx)
	cancel()
	// Give the cleanup goroutine a moment, then ensure publish is still safe.
	time.Sleep(20 * time.Millisecond)
	p.Publish(proto.Event{Topic: "after-cancel"})
}

func TestClosedPump(t *testing.T) {
	p := New(8)
	ctx := context.Background()
	ch := p.Subscribe(ctx)
	p.Close()
	p.Publish(proto.Event{Topic: "ignored"}) // must not panic
	if _, open := <-ch; open {
		t.Fatal("channel should be closed after pump Close")
	}
	// Subscribing after close returns a closed channel.
	ch2 := p.Subscribe(ctx)
	if _, open := <-ch2; open {
		t.Fatal("post-close subscription should be closed")
	}
}
