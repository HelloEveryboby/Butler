package main

import (
	"bufio"
	"container/heap"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"
)

// --- BHL 协议基础结构 ---

type Request struct {
	Jsonrpc  string                 `json:"jsonrpc"`
	Method   string                 `json:"method"`
	Params   map[string]interface{} `json:"params"`
	Id       string                 `json:"id"`
	Priority int                    `json:"priority,omitempty"` // 优先级: 0 为最高, 10 为最低
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

// --- 任务调度优先级队列 ---

type InternalTask struct {
	req      Request
	priority int
	index    int
}

type PriorityQueue []*InternalTask

func (pq PriorityQueue) Len() int { return len(pq) }
func (pq PriorityQueue) Less(i, j int) bool { return pq[i].priority < pq[j].priority }
func (pq PriorityQueue) Swap(i, j int) {
	pq[i], pq[j] = pq[j], pq[i]
	pq[i].index = i
	pq[j].index = j
}
func (pq *PriorityQueue) Push(x interface{}) {
	n := len(*pq)
	item := x.(*InternalTask)
	item.index = n
	*pq = append(*pq, item)
}
func (pq *PriorityQueue) Pop() interface{} {
	old := *pq
	n := len(old)
	item := old[n-1]
	old[n-1] = nil
	item.index = -1
	*pq = old[0 : n-1]
	return item
}

// --- 全局上下文与并发同步控制 ---

var (
	ctx, cancel = context.WithCancel(context.Background())
	taskChan    = make(chan Request, 50)
	outputMu    sync.Mutex
	workerCount = runtime.NumCPU()
	pq          = &PriorityQueue{}
	pqMu        sync.Mutex
	pqCond      = sync.NewCond(&pqMu)
)

// --- 专业级多线程功能实现 ---

// 1. 多线程文件完整性审计
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

// 2. 高性能并行正则表达式日志扫描
func scanLogFile(path string, pattern *regexp.Regexp) []string {
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()

	var matches []string
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if pattern.MatchString(line) {
			matches = append(matches, line)
		}
	}
	return matches
}

func runLogScan(dir string, regexStr string, id string) {
	re, err := regexp.Compile(regexStr)
	if err != nil {
		sendError(id, -1, "正则表达式无效: "+err.Error())
		return
	}

	sendEvent("scan_started", map[string]interface{}{"directory": dir, "regex": regexStr})

	var files []string
	filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() {
			ext := strings.ToLower(filepath.Ext(path))
			if ext == ".log" || ext == ".txt" || ext == ".go" || ext == ".sh" || ext == ".json" || ext == ".py" {
				files = append(files, path)
			}
		}
		return nil
	})

	results := make(map[string][]string)
	var mu sync.Mutex
	var wg sync.WaitGroup
	sem := make(chan struct{}, 8)

	for _, f := range files {
		wg.Add(1)
		go func(file string) {
			defer wg.Done()
			sem <- struct{}{}
			matches := scanLogFile(file, re)
			if len(matches) > 0 {
				mu.Lock()
				results[file] = matches
				mu.Unlock()
			}
			<-sem
		}(f)
	}

	wg.Wait()
	sendResult(id, results)
}

// 3. UDP 节点发现与分布式指令下发
func startDiscoveryListener(port int) {
	addr, _ := net.ResolveUDPAddr("udp", fmt.Sprintf(":%d", port))
	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		return
	}
	defer conn.Close()

	buffer := make([]byte, 1024)
	for {
		select {
		case <-ctx.Done():
			return
		default:
			conn.SetReadDeadline(time.Now().Add(1 * time.Second))
			n, remoteAddr, err := conn.ReadFromUDP(buffer)
			if err != nil {
				continue
			}
			msg := string(buffer[:n])
			if msg == "BUTLER_DISCOVER" {
				hostname, _ := os.Hostname()
				resp := fmt.Sprintf("BUTLER_NODE:%s:%d", hostname, runtime.NumCPU())
				conn.WriteToUDP([]byte(resp), remoteAddr)
			} else if strings.HasPrefix(msg, "BUTLER_CMD:") {
				cmd := strings.TrimPrefix(msg, "BUTLER_CMD:")
				resp := fmt.Sprintf("BUTLER_ACK:%s:RECEIVED_%s", os.Getenv("HOSTNAME"), cmd)
				conn.WriteToUDP([]byte(resp), remoteAddr)
			}
		}
	}
}

func dispatchRemoteCmd(port int, targetIP string, cmd string, id string) {
	addr, _ := net.ResolveUDPAddr("udp", fmt.Sprintf("%s:%d", targetIP, port))
	conn, err := net.DialUDP("udp", nil, addr)
	if err != nil {
		sendError(id, -1, "指令分发失败: "+err.Error())
		return
	}
	defer conn.Close()

	payload := "BUTLER_CMD:" + cmd
	conn.Write([]byte(payload))

	buffer := make([]byte, 1024)
	conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	n, _, err := conn.ReadFrom(buffer)
	if err != nil {
		sendError(id, -1, "远程节点超时: "+err.Error())
		return
	}

	sendResult(id, map[string]string{"node_response": string(buffer[:n])})
}

// 4. 移动设备专业审计 (Android ADB)
func getADBDevices() []string {
	out, err := exec.Command("adb", "devices").Output()
	if err != nil {
		return nil
	}
	lines := strings.Split(string(out), "\n")
	var devices []string
	for _, line := range lines {
		if strings.HasSuffix(line, "\tdevice") {
			devices = append(devices, strings.TrimSuffix(line, "\tdevice"))
		}
	}
	return devices
}

func auditADBDevice(serial string) map[string]interface{} {
	info := make(map[string]interface{})
	info["serial"] = serial

	// 获取型号
	model, _ := exec.Command("adb", "-s", serial, "shell", "getprop", "ro.product.model").Output()
	info["model"] = strings.TrimSpace(string(model))

	// 获取安卓版本
	ver, _ := exec.Command("adb", "-s", serial, "shell", "getprop", "ro.build.version.release").Output()
	info["android_ver"] = strings.TrimSpace(string(ver))

	// 检查 Root 状态 (尝试执行 id 命令)
	rootCheck, _ := exec.Command("adb", "-s", serial, "shell", "su", "-c", "id").Output()
	info["is_rooted"] = strings.Contains(string(rootCheck), "uid=0")

	// 检查安全补丁日期
	patch, _ := exec.Command("adb", "-s", serial, "shell", "getprop", "ro.build.version.security_patch").Output()
	info["security_patch"] = strings.TrimSpace(string(patch))

	return info
}

func runADBAudit(id string) {
	devices := getADBDevices()
	if len(devices) == 0 {
		sendResult(id, []string{})
		return
	}

	results := make([]map[string]interface{}, 0)
	var mu sync.Mutex
	var wg sync.WaitGroup

	for _, d := range devices {
		wg.Add(1)
		go func(serial string) {
			defer wg.Done()
			audit := auditADBDevice(serial)
			mu.Lock()
			results = append(results, audit)
			mu.Unlock()
		}(d)
	}

	wg.Wait()
	sendResult(id, results)
}

// --- 任务调度器逻辑 ---

func scheduler() {
	for {
		select {
		case <-ctx.Done():
			return
		case req := <-taskChan:
			pqMu.Lock()
			priority := 5
			if req.Priority > 0 {
				priority = req.Priority
			}
			heap.Push(pq, &InternalTask{req: req, priority: priority})
			pqCond.Signal()
			pqMu.Unlock()
		}
	}
}

func worker() {
	for {
		pqMu.Lock()
		for pq.Len() == 0 {
			pqCond.Wait()
			select {
			case <-ctx.Done():
				pqMu.Unlock()
				return
			default:
			}
		}
		item := heap.Pop(pq).(*InternalTask)
		pqMu.Unlock()

		processRequest(item.req)
	}
}

func processRequest(req Request) {
	switch req.Method {
	case "audit":
		dir, _ := req.Params["dir"].(string)
		go func() {
			var files []string
			filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
				if err == nil && !info.IsDir() {
					files = append(files, path)
				}
				return nil
			})
			results := make([]map[string]interface{}, 0)
			var mu sync.Mutex
			var wg sync.WaitGroup
			sem := make(chan struct{}, 10)
			for _, f := range files {
				wg.Add(1)
				go func(file string) {
					defer wg.Done()
					sem <- struct{}{}
					res := auditFile(file)
					mu.Lock()
					results = append(results, res)
					mu.Unlock()
					<-sem
				}(f)
			}
			wg.Wait()
			sendResult(req.Id, results)
		}()

	case "log_scan":
		dir, _ := req.Params["dir"].(string)
		regex, _ := req.Params["regex"].(string)
		go runLogScan(dir, regex, req.Id)

	case "remote_dispatch":
		ip, _ := req.Params["ip"].(string)
		cmd, _ := req.Params["cmd"].(string)
		go dispatchRemoteCmd(9999, ip, cmd, req.Id)

	case "adb_audit":
		go runADBAudit(req.Id)

	case "get_stats":
		var m runtime.MemStats
		runtime.ReadMemStats(&m)
		sendResult(req.Id, map[string]interface{}{
			"workers":    workerCount,
			"goroutines": runtime.NumGoroutine(),
			"alloc_mb":   m.Alloc / 1024 / 1024,
			"sys_mb":     m.Sys / 1024 / 1024,
			"pq_len":     pq.Len(),
		})

	case "discover_nodes":
		go func() {
			addr, _ := net.ResolveUDPAddr("udp", "255.255.255.255:9999")
			conn, _ := net.DialUDP("udp", nil, addr)
			defer conn.Close()
			conn.Write([]byte("BUTLER_DISCOVER"))
			nodes := make([]string, 0)
			conn.SetReadDeadline(time.Now().Add(2 * time.Second))
			buffer := make([]byte, 1024)
			for {
				n, remoteAddr, err := conn.ReadFrom(buffer)
				if err != nil {
					break
				}
				nodes = append(nodes, fmt.Sprintf("%s -> %s", remoteAddr.String(), string(buffer[:n])))
			}
			sendResult(req.Id, nodes)
		}()

	case "exit":
		cancel()
		os.Exit(0)

	default:
		sendError(req.Id, -32601, "方法未找到")
	}
}

func main() {
	heap.Init(pq)
	go scheduler()
	for i := 0; i < workerCount; i++ {
		go worker()
	}
	go startDiscoveryListener(9999)

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigChan
		cancel()
		os.Exit(0)
	}()

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
		taskChan <- req
	}
}

// --- 响应发送辅助函数 ---

func sendResult(id string, result interface{}) {
	resp := Response{Jsonrpc: "2.0", Result: result, Id: id}
	b, _ := json.Marshal(resp)
	outputMu.Lock()
	defer outputMu.Unlock()
	fmt.Println(string(b))
}

func sendError(id string, code int, message string) {
	resp := Response{Jsonrpc: "2.0", Error: map[string]interface{}{"code": code, "message": message}, Id: id}
	b, _ := json.Marshal(resp)
	outputMu.Lock()
	defer outputMu.Unlock()
	fmt.Println(string(b))
}

func sendEvent(method string, params interface{}) {
	event := Event{Jsonrpc: "2.0", Method: method, Params: params}
	b, _ := json.Marshal(event)
	outputMu.Lock()
	defer outputMu.Unlock()
	fmt.Println(string(b))
}
