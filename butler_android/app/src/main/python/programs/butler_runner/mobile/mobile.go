package mobile

import (
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/gorilla/websocket"
)

// ButlerEventListener defines the interface for Android to receive kernel updates
// This is used via gomobile bind to create a Java/Kotlin listener
type ButlerEventListener interface {
	OnStatusUpdate(status string)
	OnLog(message string)
	OnMetricsUpdate(jsonMetrics string)
	OnDrasStateChanged(cpuUsage float64, throttleActive bool)
	OnClusterDiscovered(deviceName string, ipAddress string)
	OnThrottlingTriggered(active bool)
}

type Runner struct {
	serverURL   string
	token       string
	id          string
	conn        *websocket.Conn
	mu          sync.Mutex
	listener    ButlerEventListener
	running     bool
	isThrottled bool
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

// Start starts the core loop and attaches a listener
func (r *Runner) Start(configJSON string, l ButlerEventListener) {
	r.mu.Lock()
	if r.running {
		r.mu.Unlock()
		return
	}
	r.running = true
	r.listener = l
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
	// High-frequency metrics simulation/reporting
	go r.metricsLoop()
	// Watch for child process signals (SIGCHLD)
	go r.watchChildProcesses()
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
	if r.listener != nil {
		r.listener.OnStatusUpdate(status)
	}
}

func (r *Runner) emitLog(msg string) {
	if r.listener != nil {
		r.listener.OnLog(msg)
	}
}

func (r *Runner) metricsLoop() {
	for {
		r.mu.Lock()
		if !r.running {
			r.mu.Unlock()
			break
		}
		r.mu.Unlock()

		// High-frequency Metrics for SubstrateHeatmap
		metrics := map[string]interface{}{
			"timestamp": time.Now().UnixMilli(),
			"cpu":       25.5, // Mock data, would be real in production
			"mem":       42.1,
			"net":       12.8,
			"throttled": r.isThrottled,
		}
		data, _ := json.Marshal(metrics)
		if r.listener != nil {
			r.listener.OnMetricsUpdate(string(data))
		}
		time.Sleep(200 * time.Millisecond)
	}
}

// UpdateSystemState is called by Java with thermal and battery info
func (r *Runner) UpdateSystemState(temp float64, battery int, isCharging bool) {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Mobile-specific DRAS: Thermal and Battery thresholds
	shouldThrottle := !isCharging && (temp > 42.0 || battery < 20)

	if shouldThrottle != r.isThrottled {
		r.isThrottled = shouldThrottle
		if r.listener != nil {
			r.listener.OnThrottlingTriggered(r.isThrottled)
		}
	}
}

func (r *Runner) watchChildProcesses() {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGCHLD)

	for {
		r.mu.Lock()
		if !r.running {
			r.mu.Unlock()
			break
		}
		r.mu.Unlock()

		select {
		case <-sigChan:
			// Capture Python sub-process or Skill exit
			r.emitLog("[Watchdog] Child process state changed. Running state clearing...")
			// Implementation would include clearing file locks etc.
		case <-time.After(1 * time.Second):
			// Just a heartbeat to check if r.running changed
		}
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
		// Handle tasks here
	}
}
