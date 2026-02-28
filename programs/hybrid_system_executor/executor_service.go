package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"runtime"
	"sync"
	"time"
)

// --- BHL Protocol Structures ---

type Request struct {
	Jsonrpc string                 `json:"jsonrpc"`
	Method  string                 `json:"method"`
	Params  map[string]interface{} `json:"params"`
	Id      string                 `json:"id"`
}

type Response struct {
	Jsonrpc string      `json:"jsonrpc"`
	Result  interface{} `json:"result,omitempty"`
	Error   interface{} `json:"error,omitempty"`
	Id      string      `json:"id"`
}

type Event struct {
	Jsonrpc string      `json:"jsonrpc"`
	Method  string      `json:"method"`
	Params  interface{} `json:"params"`
}

// --- Multi-threaded Features ---

var (
	workerCount = runtime.NumCPU()
	outputMu    sync.Mutex
)

func auditFile(path string) map[string]interface{} {
	f, err := os.Open(path)
	if err != nil {
		return map[string]interface{}{"path": path, "error": err.Error()}
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return map[string]interface{}{"path": path, "error": err.Error()}
	}

	return map[string]interface{}{
		"path": path,
		"hash": hex.EncodeToString(h.Sum(nil)),
	}
}

func runAudit(dir string, id string) {
	sendEvent("audit_started", map[string]interface{}{"directory": dir})

	var files []string
	filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() {
			files = append(files, path)
		}
		return nil
	})

	results := make([]map[string]interface{}, 0)
	var mu sync.Mutex
	var innerWg sync.WaitGroup

	// Limit concurrency for file audit to avoid too many open files
	sem := make(chan struct{}, 10)

	for _, f := range files {
		innerWg.Add(1)
		go func(file string) {
			defer innerWg.Done()
			sem <- struct{}{}
			res := auditFile(file)
			mu.Lock()
			results = append(results, res)
			mu.Unlock()
			<-sem
		}(f)
	}

	innerWg.Wait()
	sendResult(id, results)
}

// --- Node Discovery (UDP) ---

func startDiscovery(port int) {
	addr, err := net.ResolveUDPAddr("udp", fmt.Sprintf(":%d", port))
	if err != nil {
		return
	}
	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		return
	}
	defer conn.Close()

	buffer := make([]byte, 1024)
	for {
		n, remoteAddr, err := conn.ReadFromUDP(buffer)
		if err != nil {
			continue
		}
		msg := string(buffer[:n])
		if msg == "BUTLER_DISCOVER" {
			hostname, _ := os.Hostname()
			resp := fmt.Sprintf("BUTLER_NODE:%s:%d", hostname, runtime.NumCPU())
			conn.WriteToUDP([]byte(resp), remoteAddr)
		}
	}
}

func broadcastDiscovery(port int, timeout time.Duration, id string) {
	addr, _ := net.ResolveUDPAddr("udp", fmt.Sprintf("255.255.255.255:%d", port))
	conn, err := net.DialUDP("udp", nil, addr)
	if err != nil {
		sendError(id, -1, "Failed to create UDP broadcast: "+err.Error())
		return
	}
	defer conn.Close()

	conn.Write([]byte("BUTLER_DISCOVER"))

	nodes := make([]string, 0)
	conn.SetReadDeadline(time.Now().Add(timeout))
	buffer := make([]byte, 1024)

	for {
		n, remoteAddr, err := conn.ReadFrom(buffer)
		if err != nil {
			break
		}
		nodes = append(nodes, fmt.Sprintf("%s -> %s", remoteAddr.String(), string(buffer[:n])))
	}

	sendResult(id, nodes)
}

// --- Main Loop ---

func main() {
	go startDiscovery(9999) // Background discovery listener

	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		line := scanner.Text()
		if line == "" {
			continue
		}

		var req Request
		if err := json.Unmarshal([]byte(line), &req); err != nil {
			continue
		}

		switch req.Method {
		case "audit":
			dir, _ := req.Params["dir"].(string)
			go runAudit(dir, req.Id)

		case "discover_nodes":
			go broadcastDiscovery(9999, 2*time.Second, req.Id)

		case "get_stats":
			var m runtime.MemStats
			runtime.ReadMemStats(&m)
			sendResult(req.Id, map[string]interface{}{
				"workers":    workerCount,
				"goroutines": runtime.NumGoroutine(),
				"alloc_mb":   m.Alloc / 1024 / 1024,
				"sys_mb":     m.Sys / 1024 / 1024,
				"os":         runtime.GOOS,
				"arch":       runtime.GOARCH,
			})

		case "exit":
			os.Exit(0)

		default:
			sendError(req.Id, -32601, "Method not found")
		}
	}
}

// --- Helpers ---

func sendResult(id string, result interface{}) {
	resp := Response{
		Jsonrpc: "2.0",
		Result:  result,
		Id:      id,
	}
	b, _ := json.Marshal(resp)
	outputMu.Lock()
	defer outputMu.Unlock()
	fmt.Println(string(b))
}

func sendError(id string, code int, message string) {
	resp := Response{
		Jsonrpc: "2.0",
		Error: map[string]interface{}{
			"code":    code,
			"message": message,
		},
		Id: id,
	}
	b, _ := json.Marshal(resp)
	outputMu.Lock()
	defer outputMu.Unlock()
	fmt.Println(string(b))
}

func sendEvent(method string, params interface{}) {
	event := Event{
		Jsonrpc: "2.0",
		Method:  method,
		Params:  params,
	}
	b, _ := json.Marshal(event)
	outputMu.Lock()
	defer outputMu.Unlock()
	fmt.Println(string(b))
}
