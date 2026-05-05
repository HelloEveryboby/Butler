package mobile

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// MobileCallback defines the interface for Flutter to receive updates
type MobileCallback interface {
	OnStatusUpdate(status string)
	OnLog(message string)
}

type Runner struct {
	serverURL string
	token     string
	id        string
	conn      *websocket.Conn
	mu        sync.Mutex
	callback  MobileCallback
	running   bool
}

type Message struct {
	Type     string `json:"type"`
	Payload  string `json:"payload"`
	Token    string `json:"token"`
	RunnerID string `json:"runner_id,omitempty"`
}

func NewRunner() *Runner {
	return &Runner{
		running: false,
	}
}

func (r *Runner) Start(configJSON string, cb MobileCallback) {
	r.mu.Lock()
	if r.running {
		r.mu.Unlock()
		return
	}
	r.running = true
	r.callback = cb
	r.mu.Unlock()

	var config struct {
		ServerURL string `json:"server_url"`
		Token     string `json:"token"`
		ID        string `json:"id"`
	}

	err := json.Unmarshal([]byte(configJSON), &config)
	if err != nil {
		r.emitLog(fmt.Sprintf("Config error: %v", err))
		return
	}

	r.serverURL = config.ServerURL
	r.token = config.Token
	r.id = config.ID

	go r.runLoop()
}

func (r *Runner) Stop() {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.running = false
	if r.conn != nil {
		r.conn.Close()
	}
	r.emitStatus("Stopped")
}

func (r *Runner) emitStatus(status string) {
	if r.callback != nil {
		r.callback.OnStatusUpdate(status)
	}
}

func (r *Runner) emitLog(msg string) {
	if r.callback != nil {
		r.callback.OnLog(msg)
	}
}

func (r *Runner) runLoop() {
	for {
		r.mu.Lock()
		if !r.running {
			r.mu.Unlock()
			break
		}
		r.mu.Unlock()

		err := r.connect()
		if err != nil {
			r.emitLog(fmt.Sprintf("Connect failed: %v, retrying...", err))
			time.Sleep(5 * time.Second)
			continue
		}
	}
}

func (r *Runner) connect() error {
	c, _, err := websocket.DefaultDialer.Dial(r.serverURL, nil)
	if err != nil {
		return err
	}
	r.mu.Lock()
	r.conn = c
	r.mu.Unlock()
	defer func() {
		r.mu.Lock()
		r.conn = nil
		r.mu.Unlock()
		c.Close()
	}()

	r.emitStatus("Connected")
	r.emitLog("Successfully connected to Butler System")

	regMsg := Message{
		Type:     "register",
		Token:    r.token,
		RunnerID: r.id,
	}
	if err := c.WriteJSON(regMsg); err != nil {
		return err
	}

	for {
		_, message, err := c.ReadMessage()
		if err != nil {
			return err
		}

		var msg Message
		if err := json.Unmarshal(message, &msg); err != nil {
			r.emitLog(fmt.Sprintf("Invalid message: %v", err))
			continue
		}

		if msg.Token != r.token {
			r.emitLog("Auth failed, ignoring message")
			continue
		}

		r.emitLog(fmt.Sprintf("Received task: %s", msg.Type))
		// Mobile specific task handling could be added here
	}
}
