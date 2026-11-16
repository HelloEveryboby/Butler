// Package events provides the connector's bounded fan-out event pump.
//
// Producers publish session/plugin events without blocking; each subscriber
// gets an independent bounded queue with a drop-oldest policy. Dropped-event
// accounting is exposed so operators can detect slow consumers instead of
// silently losing observability data.
package events

import (
	"context"
	"sync"
	"sync/atomic"

	"github.com/HelloEveryboby/Butler/connector/internal/proto"
)

// DefaultBuffer is the per-subscriber queue depth.
const DefaultBuffer = 256

type subscriber struct {
	ch     chan proto.Event
	closed bool
}

// Pump is a broadcast hub for proto.Event values.
type Pump struct {
	mu       sync.Mutex
	subs     map[int]*subscriber
	nextID   int
	bufSize  int
	dropped  atomic.Uint64
	closed   bool
}

// New creates a pump with the given per-subscriber buffer depth.
func New(buffer int) *Pump {
	if buffer <= 0 {
		buffer = DefaultBuffer
	}
	return &Pump{
		subs:    make(map[int]*subscriber),
		bufSize: buffer,
	}
}

// Subscribe registers a consumer. The returned channel is closed when the
// context is done or the pump is closed.
func (p *Pump) Subscribe(ctx context.Context) <-chan proto.Event {
	p.mu.Lock()
	if p.closed {
		p.mu.Unlock()
		ch := make(chan proto.Event)
		close(ch)
		return ch
	}
	id := p.nextID
	p.nextID++
	sub := &subscriber{ch: make(chan proto.Event, p.bufSize)}
	p.subs[id] = sub
	p.mu.Unlock()

	go func() {
		<-ctx.Done()
		p.unsubscribe(id)
	}()
	return sub.ch
}

// Publish delivers an event to every subscriber without blocking. When a
// subscriber's queue is full the oldest event is dropped and accounted for.
func (p *Pump) Publish(ev proto.Event) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return
	}
	for _, sub := range p.subs {
		if sub.closed {
			continue
		}
		select {
		case sub.ch <- ev:
		default:
			// Drop-oldest keeps the freshest signal for slow consumers.
			select {
			case <-sub.ch:
			default:
			}
			select {
			case sub.ch <- ev:
			default:
			}
			p.dropped.Add(1)
		}
	}
}

// Dropped returns the total number of events discarded due to backpressure.
func (p *Pump) Dropped() uint64 { return p.dropped.Load() }

// Close shuts down all subscriber channels exactly once.
func (p *Pump) Close() {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.closed {
		return
	}
	p.closed = true
	for id, sub := range p.subs {
		if !sub.closed {
			sub.closed = true
			close(sub.ch)
		}
		delete(p.subs, id)
	}
}

func (p *Pump) unsubscribe(id int) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if sub, ok := p.subs[id]; ok && !sub.closed {
		sub.closed = true
		close(sub.ch)
		delete(p.subs, id)
	}
}
