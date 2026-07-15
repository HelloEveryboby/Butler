package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"image/jpeg"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/go-vgo/robotgo"
	"github.com/gorilla/websocket"
	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"
	"github.com/vova616/screenshot"
	"github.com/butler/programs/butler_runner/storage_hub"
	"butler_runner/converter"
)

// --- 协议定义 ---
type Message struct {
	Type               string                 `json:"type"`    // cmd, shell, file_ls, screenshot, input, sys_info, ping, pong, register, sleep, spawn_skill
	Payload            string                 `json:"payload"` // 指令内容或路径
	Data               interface{}            `json:"data,omitempty"`
	Token              string                 `json:"token"`
	RunnerID           string                 `json:"runner_id,omitempty"`
	BlackboardSnapshot map[string]interface{} `json:"blackboard_snapshot,omitempty"`
	SkillConfig        *SkillSpawnConfig      `json:"skill_config,omitempty"`
	RequestID          string                 `json:"request_id,omitempty"`
}

type SkillSpawnConfig struct {
	ID            string            `json:"id"`
	Path          string            `json:"path"`
	Args          []string          `json:"args"`
	Env           map[string]string `json:"env"`
	Risk          string            `json:"risk"`
	IsLongRunning bool              `json:"is_long_running"`
}

type Response struct {
	Status    string      `json:"status"`
	Data      interface{} `json:"data,omitempty"`
	Error     string      `json:"error,omitempty"`
	RunnerID  string      `json:"runner_id"`
	RequestID string      `json:"request_id,omitempty"`
}

type EnvInfo struct {
	OS             string   `json:"os"`
	Arch           string   `json:"arch"`
	DefaultShell   string   `json:"default_shell"`
	AvailableTools []string `json:"available_tools"`
	IsAdmin        bool     `json:"is_admin"`
}

func detectEnvironment() EnvInfo {
	isAdminUser := false
	if runtime.GOOS == "windows" {
		f, err := os.Open("\\\\.\\PHYSICALDRIVE0")
		if err == nil {
			isAdminUser = true
			f.Close()
		}
	} else {
		isAdminUser = (os.Getuid() == 0 || os.Geteuid() == 0)
	}

	var availableTools []string
	toolsToCheck := []string{"python", "python3", "ffmpeg", "pandoc", "libreoffice", "soffice", "git", "zip", "unzip", "tar"}
	for _, tool := range toolsToCheck {
		if _, err := exec.LookPath(tool); err == nil {
			availableTools = append(availableTools, tool)
		}
	}

	defaultShell := "sh"
	if runtime.GOOS == "windows" {
		if val := os.Getenv("COMSPEC"); val != "" {
			defaultShell = val
		} else if _, err := exec.LookPath("powershell"); err == nil {
			defaultShell = "powershell"
		} else {
			defaultShell = "cmd"
		}
	} else {
		if val := os.Getenv("SHELL"); val != "" {
			defaultShell = val
		} else if _, err := exec.LookPath("bash"); err == nil {
			defaultShell = "/bin/bash"
		}
	}

	return EnvInfo{
		OS:             runtime.GOOS,
		Arch:           runtime.GOARCH,
		DefaultShell:   defaultShell,
		AvailableTools: availableTools,
		IsAdmin:        isAdminUser,
	}
}

var (
	serverURL    = flag.String("server", "ws://localhost:8000/ws/butler", "Butler server WebSocket URL")
	authToken    = flag.String("token", "", "Authentication token (REQUIRED)")
	runnerID     = flag.String("id", "default_runner", "Unique ID for this runner")
	isSleeping   = false
	mu           sync.Mutex
	blackboard   = make(map[string]interface{})
	vault        = NewVaultEngine()
	procMgr      *ProcessManager
	storageMgr   = storage_hub.NewStorageManager()
	activeCmds   = make(map[string]context.CancelFunc)
	activeCmdsMu sync.Mutex
)

// --- Hardware Capability Detection ---

func getHardwareCapabilities() map[string]interface{} {
	v, _ := mem.VirtualMemory()
	c, _ := cpu.Counts(true)
	return map[string]interface{}{
		"total_mem": v.Total,
		"cpu_cores": c,
		"low_power": v.Total < 1024*1024*1024 || c < 2, // < 1GB or < 2 cores
		"os":        runtime.GOOS,
		"arch":      runtime.GOARCH,
	}
}

// --- Process Manager (Shadow Daemon) ---

type ManagedProcess struct {
	Config       *SkillSpawnConfig
	Cmd          *exec.Cmd
	RestartCount int
	LastStart    time.Time
	mu           sync.Mutex
	Cancel       context.CancelFunc
}

type ProcessManager struct {
	processes map[string]*ManagedProcess
	mu        sync.Mutex
	conn      *websocket.Conn
}

func NewProcessManager(c *websocket.Conn) *ProcessManager {
	return &ProcessManager{
		processes: make(map[string]*ManagedProcess),
		conn:      c,
	}
}

func (pm *ProcessManager) Spawn(config *SkillSpawnConfig) error {
	pm.mu.Lock()
	if old, exists := pm.processes[config.ID]; exists {
		old.Stop()
	}
	mp := &ManagedProcess{Config: config}
	pm.processes[config.ID] = mp
	pm.mu.Unlock()

	return pm.startProcess(mp)
}

func (pm *ProcessManager) startProcess(mp *ManagedProcess) error {
	mp.mu.Lock()
	defer mp.mu.Unlock()

	ctx, cancel := context.WithCancel(context.Background())
	mp.Cancel = cancel

	cmd := exec.CommandContext(ctx, mp.Config.Path, mp.Config.Args...)
	cmd.Dir = filepath.Dir(mp.Config.Path)

	// Environment Injection
	env := os.Environ()
	for k, v := range mp.Config.Env {
		env = append(env, fmt.Sprintf("%s=%s", k, v))
	}
	cmd.Env = env

	// OS-level Resource Management & Priority
	pm.applyResourceLimits(cmd, mp.Config.Risk)

	// Standard I/O redirection (Capture for Snapshot Engine)
	stdout, _ := cmd.StdoutPipe()
	stderr, _ := cmd.StderrPipe()

	err := cmd.Start()
	if err != nil {
		return err
	}

	mp.Cmd = cmd
	mp.LastStart = time.Now()
	mp.RestartCount++

	// Goroutine to monitor lifecycle
	go pm.monitorProcess(mp, stdout, stderr)

	return nil
}


func (pm *ProcessManager) monitorProcess(mp *ManagedProcess, stdout, stderr io.ReadCloser) {
	// Snapshot engine would read from these pipes
	go func() {
		scanner := io.TeeReader(stdout, os.Stdout) // Just for local log for now
		io.Copy(io.Discard, scanner)
	}()
	go func() {
		io.Copy(io.Discard, stderr)
	}()

	err := mp.Cmd.Wait()

	// Check if we should restart (Self-healing)
	if mp.Config.IsLongRunning {
		exitCode := 0
		if err != nil {
			if exiterr, ok := err.(*exec.ExitError); ok {
				if status, ok := exiterr.Sys().(syscall.WaitStatus); ok {
					exitCode = status.ExitStatus()
				}
			}
		}

		fmt.Printf("⚠️ Skill %s exited with code %d. Self-healing in progress...\n", mp.Config.ID, exitCode)

		// Exponential Backoff
		backoff := time.Duration(mp.RestartCount) * time.Second
		if backoff > 30*time.Second {
			backoff = 30 * time.Second
		}

		time.Sleep(backoff)

		// Cleanup legacy files as requested
		pm.cleanupLegacyFiles(mp.Config.Path)

		pm.startProcess(mp)
	}
}

func (pm *ProcessManager) cleanupLegacyFiles(path string) {
	dir := filepath.Dir(path)
	// Clear __pycache__
	pycache := filepath.Join(dir, "__pycache__")
	os.RemoveAll(pycache)

	// Clear *.pid and *.lock
	files, _ := os.ReadDir(dir)
	for _, f := range files {
		if strings.HasSuffix(f.Name(), ".pid") || strings.HasSuffix(f.Name(), ".lock") {
			os.Remove(filepath.Join(dir, f.Name()))
		}
	}
}

func (mp *ManagedProcess) Stop() {
	mp.mu.Lock()
	defer mp.mu.Unlock()
	if mp.Cancel != nil {
		mp.Cancel()
	}
}

// --- DWT (Dynamic Watermark Throttle) ---

func getCPUUsage() float64 {
	percent, err := cpu.Percent(0, false)
	if err != nil || len(percent) == 0 {
		return 0
	}
	return percent[0]
}

func executeWithThrottle(ctx context.Context, task func()) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
			usage := getCPUUsage()
			if usage > 85 {
				time.Sleep(100 * time.Millisecond) // 红区
			} else if usage > 60 {
				time.Sleep(10 * time.Millisecond) // 黄区
			}
			task()
		}
	}
}

func main() {
	flag.Parse()

	if *authToken == "" {
		fmt.Println("❌ ERROR: Auth token is required. Use -token to specify it.")
		os.Exit(1)
	}

	if *authToken == "BUTLER_SECRET_2026" {
		fmt.Println("⚠️ WARNING: Using a default or insecure token. Please change it for production use.")
	}

	// Signal handling for clean shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	fmt.Printf("🚀 Butler-Runner Pro [%s] 启动中...\n", *runnerID)
	fmt.Printf("🔗 连接至: %s\n", *serverURL)

	snapshotEngine.Start()

	go func() {
		for {
			if err := connect(); err != nil {
				log.Printf("❌ 连接失败: %v, 5秒后重连...", err)
				time.Sleep(5 * time.Second)
				continue
			}
		}
	}()

	<-sigChan
	fmt.Println("👋 Butler-Runner shutting down...")
}

func connect() error {
	c, _, err := websocket.DefaultDialer.Dial(*serverURL, nil)
	if err != nil {
		return err
	}
	defer c.Close()
	fmt.Println("✅ 已成功连接至 Butler 主系统")

	procMgr = NewProcessManager(c)

	envInfo := detectEnvironment()

	// 发送注册消息
	regMsg := Message{
		Type:     "register",
		Token:    *authToken,
		RunnerID: *runnerID,
		Data:     envInfo,
	}
	if err := c.WriteJSON(regMsg); err != nil {
		return err
	}

	for {
		_, message, err := c.ReadMessage()
		if err != nil {
			log.Printf("❌ 读取消息失败: %v", err)
			return err
		}

		var msg Message
		if err := json.Unmarshal(message, &msg); err != nil {
			log.Printf("⚠️ 消息格式错误: %v", err)
			continue
		}

		if msg.Token != *authToken {
			log.Println("🚫 身份验证失败，忽略消息")
			continue
		}

		// 唤醒机制
		mu.Lock()
		if isSleeping {
			fmt.Println("🌅 收到指令，正在唤醒...")
			isSleeping = false
		}
		mu.Unlock()

		// 更新本地影子黑板
		if msg.BlackboardSnapshot != nil {
			mu.Lock()
			for k, v := range msg.BlackboardSnapshot {
				blackboard[k] = v
			}
			mu.Unlock()
		}

		// 核心指令分发
		go func() {
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()

			executeWithThrottle(ctx, func() {
				handleTask(c, msg)
				cancel() // 执行完一次任务后退出 throttle 循环
			})
		}()

		// Metrics Broadcasting (Load-aware frame skipping)
		go func() {
			usage := getCPUUsage()
			if usage > 95 {
				time.Sleep(1 * time.Second) // Critical load: skip metrics
			} else if usage > 85 {
				time.Sleep(500 * time.Millisecond) // High load: slow metrics
			} else {
				time.Sleep(200 * time.Millisecond)
			}

			latest := snapshotEngine.GetLatest()
			metricsMsg := Message{
				Type:     "metrics",
				Data:     latest,
				RunnerID: *runnerID,
				Token:    *authToken,
			}
			c.WriteJSON(metricsMsg)
		}()
	}
}

func normalizeType(t string) string {
	t = strings.ToLower(t)
	switch t {
	case "ls", "list", "列出", "列表", "file_ls", "目录", "看":
		return "file_ls"
	case "upload", "上传", "file_upload", "up", "传":
		return "file_upload"
	case "delete", "remove", "删除", "移除", "file_delete", "rm", "删":
		return "file_delete"
	case "shell", "exec", "run", "执行", "运行", "cmd", "sh", "搞":
		return "shell"
	case "cd", "切换目录", "进", "去":
		return "cd"
	case "download", "下载", "file_download", "dl", "拿":
		return "file_download"
	case "mkdir", "创建目录", "md", "建":
		return "file_mkdir"
	case "read", "读取文件", "cat", "读":
		return "file_read"
	case "screenshot", "截图", "拍":
		return "screenshot"
	case "app_control", "控制应用":
		return "app_control"
	case "input", "输入":
		return "input"
	case "sys_info", "系统信息", "机子":
		return "sys_info"
	case "sleep", "睡眠", "歇":
		return "sleep"
	case "vault_init", "vault_set_key":
		return "vault_init"
	case "vault_encrypt":
		return "vault_encrypt"
	case "vault_decrypt":
		return "vault_decrypt"
	case "spawn_skill", "spawn":
		return "spawn_skill"
	case "storage_transfer", "cloud_transfer":
		return "storage_transfer"
	case "storage_oauth_listen":
		return "storage_oauth_listen"
	default:
		return t
	}
}

func isSafePath(path string) bool {
	if path == "" || path == "/" || path == "." || path == ".." {
		return false
	}
	// Check for path traversal
	if strings.Contains(path, "..") {
		return false
	}
	// Check for absolute path in Unix or root in Windows
	if filepath.IsAbs(path) {
		// For simplicity, we only allow relative paths for file ops in this version
		// Or we can restrict to specific root if configured, but let's at least block root
		if path == "/" || (runtime.GOOS == "windows" && len(path) <= 3 && strings.HasSuffix(path, ":\\")) {
			return false
		}
	}
	return true
}

func handleTask(c *websocket.Conn, msg Message) {
	msgType := normalizeType(msg.Type)
	switch msgType {
	case "format_convert":
		var task struct {
			Input   string                   `json:"input"`
			From    string                   `json:"from"`
			To      string                   `json:"to"`
			SaveTo  string                   `json:"save_to"`
			Options converter.ConvertOptions `json:"options"`
		}
		if err := json.Unmarshal([]byte(msg.Payload), &task); err != nil {
			sendRespWithID(c, "fail", nil, "Invalid format_convert payload: "+err.Error(), msg.RequestID)
			return
		}

		// 1. Resolve source stream (Input)
		var src io.Reader
		if strings.HasPrefix(task.Input, "http://") || strings.HasPrefix(task.Input, "https://") {
			resp, err := http.Get(task.Input)
			if err != nil {
				sendRespWithID(c, "fail", nil, "HTTP download failed: "+err.Error(), msg.RequestID)
				return
			}
			defer resp.Body.Close()
			src = resp.Body
		} else if isFile, err := os.Stat(task.Input); err == nil && !isFile.IsDir() {
			if !isSafePath(task.Input) {
				sendRespWithID(c, "fail", nil, "Security error: Unsafe input file path: "+task.Input, msg.RequestID)
				return
			}
			file, err := os.Open(task.Input)
			if err != nil {
				sendRespWithID(c, "fail", nil, "Failed to open input file: "+err.Error(), msg.RequestID)
				return
			}
			defer file.Close()
			src = file
		} else {
			// Memory/string source
			src = strings.NewReader(task.Input)
		}

		// 2. Resolve target stream (SaveTo / Memory)
		var dst io.Writer
		var memBuf bytes.Buffer

		if task.SaveTo != "" {
			if !isSafePath(task.SaveTo) {
				sendRespWithID(c, "fail", nil, "Security error: Unsafe save_to file path: "+task.SaveTo, msg.RequestID)
				return
			}
			// Ensure parent directory exists
			parentDir := filepath.Dir(task.SaveTo)
			if err := os.MkdirAll(parentDir, 0755); err != nil {
				sendRespWithID(c, "fail", nil, "Failed to create save_to directory: "+err.Error(), msg.RequestID)
				return
			}
			file, err := os.Create(task.SaveTo)
			if err != nil {
				sendRespWithID(c, "fail", nil, "Failed to create target file: "+err.Error(), msg.RequestID)
				return
			}
			defer file.Close()
			dst = file
		} else {
			dst = &memBuf
		}

		// 3. Resolve converter from registry
		reg := converter.NewConverterRegistry()
		conv, exists := reg.GetConverter(converter.DocType(strings.ToUpper(task.From)), converter.DocType(strings.ToUpper(task.To)))
		if !exists {
			sendRespWithID(c, "fail", nil, fmt.Sprintf("Unsupported conversion path: %s -> %s", task.From, task.To), msg.RequestID)
			return
		}

		// 4. Run conversion
		if err := conv.Convert(context.Background(), src, dst, task.Options); err != nil {
			sendRespWithID(c, "fail", nil, "Conversion error: "+err.Error(), msg.RequestID)
			return
		}

		// 5. Respond
		if task.SaveTo != "" {
			sendRespWithID(c, "ok", "Saved to "+task.SaveTo, "", msg.RequestID)
		} else {
			sendRespWithID(c, "ok", memBuf.String(), "", msg.RequestID)
		}

	case "ping":
		sendResp(c, "pong", "alive", "")

	case "spawn_skill":
		if msg.SkillConfig == nil {
			sendResp(c, "fail", nil, "Missing skill_config")
			return
		}
		err := procMgr.Spawn(msg.SkillConfig)
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			sendResp(c, "ok", "Skill spawned and managed", "")
		}

	case "app_control":
		// Payload 格式: "start:C:\Path\To\App.exe" 或 "kill:PotPlayer.exe"
		parts := strings.SplitN(msg.Payload, ":", 2)
		if len(parts) < 2 {
			sendResp(c, "fail", nil, "Invalid app_control payload (expected action:target)")
			return
		}

		action := parts[0]
		target := parts[1]

		switch action {
		case "start":
			var cmd *exec.Cmd
			if runtime.GOOS == "windows" {
				cmd = exec.Command("cmd", "/C", "start", "", target)
			} else if runtime.GOOS == "darwin" {
				cmd = exec.Command("open", target)
			} else {
				cmd = exec.Command("xdg-open", target)
			}
			err := cmd.Start()
			if err != nil {
				sendResp(c, "fail", nil, err.Error())
			} else {
				sendResp(c, "ok", "App started", "")
			}
		case "kill":
			var cmd *exec.Cmd
			if runtime.GOOS == "windows" {
				cmd = exec.Command("taskkill", "/F", "/IM", target)
			} else {
				cmd = exec.Command("pkill", target)
			}
			output, err := cmd.CombinedOutput()
			if err != nil {
				sendResp(c, "fail", string(output), err.Error())
			} else {
				sendResp(c, "ok", "App killed", "")
			}
		case "focus":
			robotgo.ActiveName(target)
			sendResp(c, "ok", "Window focused", "")
		default:
			sendResp(c, "fail", nil, "Unknown app_control action: "+action)
		}

	case "input":
		// Payload 格式: "key:space" 或 "type:hello"
		parts := strings.SplitN(msg.Payload, ":", 2)
		if len(parts) < 2 {
			sendResp(c, "fail", nil, "Invalid input payload (expected action:value)")
			return
		}

		action := parts[0]
		value := parts[1]

		switch action {
		case "key":
			robotgo.KeyTap(value)
			sendResp(c, "ok", "Key tapped", "")
		case "click":
			robotgo.Click(value)
			sendResp(c, "ok", "Mouse clicked", "")
		case "type":
			robotgo.TypeStr(value)
			sendResp(c, "ok", "String typed", "")
		default:
			sendResp(c, "fail", nil, "Unknown input action: "+action)
		}

	case "screenshot":
		img, err := screenshot.CaptureScreen()
		if err != nil {
			sendResp(c, "fail", nil, "Failed to capture screen: "+err.Error())
			return
		}

		tempFile := "temp_screenshot.jpg"
		f, err := os.Create(tempFile)
		if err != nil {
			sendResp(c, "fail", nil, "Failed to create temp file: "+err.Error())
			return
		}

		err = jpeg.Encode(f, img, &jpeg.Options{Quality: 60})
		f.Close()
		if err != nil {
			sendResp(c, "fail", nil, "Failed to encode image: "+err.Error())
			return
		}

		buf, err := os.ReadFile(tempFile)
		if err != nil {
			sendResp(c, "fail", nil, "Failed to read temp file: "+err.Error())
			return
		}

		encoded := base64.StdEncoding.EncodeToString(buf)
		sendResp(c, "screenshot", encoded, "")
		os.Remove(tempFile)

	case "file_ls":
		path := msg.Payload
		if path == "" {
			path = "."
		}
		files, err := os.ReadDir(path)
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
			return
		}
		var fileList []string
		for _, f := range files {
			name := f.Name()
			if f.IsDir() {
				name += "/"
			}
			fileList = append(fileList, name)
		}
		sendResp(c, "ok", fileList, "")

	case "file_upload":
		// Payload 格式: "filename|base64_content"
		parts := strings.SplitN(msg.Payload, "|", 2)
		if len(parts) < 2 {
			sendResp(c, "fail", nil, "Upload requires filename and content (format: filename|base64)")
			return
		}
		filename := parts[0]
		if !isSafePath(filename) {
			sendResp(c, "fail", nil, "Unsafe upload path: "+filename)
			return
		}
		content, err := base64.StdEncoding.DecodeString(parts[1])
		if err != nil {
			sendResp(c, "fail", nil, "Base64 decode error: "+err.Error())
			return
		}
		err = os.WriteFile(filename, content, 0644)
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			sendResp(c, "ok", fmt.Sprintf("File %s uploaded (%d bytes)", filename, len(content)), "")
		}

	case "file_delete":
		if !isSafePath(msg.Payload) {
			sendResp(c, "fail", nil, "Unsafe delete path: "+msg.Payload)
			return
		}
		err := os.RemoveAll(msg.Payload)
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			sendResp(c, "ok", "Deleted: "+msg.Payload, "")
		}

	case "interrupt":
		reqID := msg.Payload // Payload contains the request_id to interrupt
		activeCmdsMu.Lock()
		cancel, exists := activeCmds[reqID]
		activeCmdsMu.Unlock()
		if exists && cancel != nil {
			cancel()
			sendRespWithID(c, "ok", "Command interrupt signal sent", "", msg.RequestID)
		} else {
			sendRespWithID(c, "fail", nil, "No active command found with request_id: "+reqID, msg.RequestID)
		}

	case "shell":
		reqID := msg.RequestID
		if reqID == "" {
			reqID = "shell_sync" // Fallback if no request_id
		}

		fmt.Printf("⚠️  Executing Shell Command [%s]: %s\n", reqID, msg.Payload)

		ctx, cancel := context.WithCancel(context.Background())
		activeCmdsMu.Lock()
		activeCmds[reqID] = cancel
		activeCmdsMu.Unlock()

		defer func() {
			activeCmdsMu.Lock()
			delete(activeCmds, reqID)
			activeCmdsMu.Unlock()
		}()

		var cmd *exec.Cmd
		if runtime.GOOS == "windows" {
			cmd = exec.CommandContext(ctx, "cmd", "/C", msg.Payload)
		} else {
			cmd = exec.CommandContext(ctx, "sh", "-c", msg.Payload)
		}

		// Use a buffer to capture stdout/stderr dynamically
		var outBuf bytes.Buffer
		cmd.Stdout = &outBuf
		cmd.Stderr = &outBuf

		err := cmd.Start()
		if err != nil {
			sendRespWithID(c, "fail", nil, err.Error(), reqID)
			return
		}

		// Wait for completion or context cancel
		err = cmd.Wait()

		// Check if it was canceled
		if ctx.Err() != nil {
			stdoutPeek := outBuf.String()
			if len(stdoutPeek) > 1000 {
				stdoutPeek = stdoutPeek[:1000] + "...[已被用户中断截断]..."
			} else {
				stdoutPeek += "...[已被用户中断截断]..."
			}
			exitCode := 130 // Default standard for SIGINT/Interrupted
			if cmd.ProcessState != nil {
				if sysStatus, ok := cmd.ProcessState.Sys().(syscall.WaitStatus); ok {
					exitCode = sysStatus.ExitStatus()
				}
			}

			sendRespWithID(c, "interrupted", map[string]interface{}{
				"exit_code":   exitCode,
				"stdout_peek": stdoutPeek,
				"stderr":      "signal: interrupt",
			}, "signal: interrupt", reqID)
			return
		}

		// Normal execution completed
		output := outBuf.String()
		if err != nil {
			sendRespWithID(c, "fail", output, err.Error(), reqID)
		} else {
			sendRespWithID(c, "ok", output, "", reqID)
		}

	case "cd":
		fmt.Printf("📂 Changing Directory to: %s\n", msg.Payload)
		err := os.Chdir(msg.Payload)
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			dir, _ := os.Getwd()
			sendResp(c, "ok", "Changed directory to: "+dir, "")
		}

	case "file_mkdir":
		if !isSafePath(msg.Payload) {
			sendResp(c, "fail", nil, "Unsafe directory path: "+msg.Payload)
			return
		}
		err := os.MkdirAll(msg.Payload, 0755)
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			sendResp(c, "ok", "Directory created: "+msg.Payload, "")
		}

	case "file_read":
		if !isSafePath(msg.Payload) {
			sendResp(c, "fail", nil, "Unsafe read path: "+msg.Payload)
			return
		}
		content, err := os.ReadFile(msg.Payload)
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			// 如果是文本则尝试直接返回，否则返回 Base64
			encoded := base64.StdEncoding.EncodeToString(content)
			sendResp(c, "ok", encoded, "")
		}

	case "file_download":
		// Payload 格式: "http://url|C:\dest\path"
		parts := strings.SplitN(msg.Payload, "|", 2)
		if len(parts) < 2 {
			sendResp(c, "fail", nil, "Download requires URL and destination path (format: url|path)")
			return
		}
		err := downloadFile(parts[0], parts[1])
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			sendResp(c, "ok", "File downloaded", "")
		}

	case "sys_info":
		info := getHardwareCapabilities()
		sendResp(c, "sys", info, "")

	case "sleep":
		mu.Lock()
		isSleeping = true
		mu.Unlock()
		fmt.Println("💤 进入睡眠模式...")
		sendResp(c, "ok", "Runner is now sleeping", "")

	case "vault_init":
		// Use hex encoding for the key
		key, err := base64.StdEncoding.DecodeString(msg.Payload)
		if err != nil {
			sendResp(c, "fail", nil, "Invalid base64 key: "+err.Error())
			return
		}
		err = vault.SetMasterKey(key)
		if err != nil {
			sendResp(c, "fail", nil, "Vault Init failed: "+err.Error())
		} else {
			sendResp(c, "ok", "Vault initialized and memory pinned", "")
		}

	case "vault_encrypt":
		res, err := vault.Encrypt([]byte(msg.Payload))
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			sendResp(c, "ok", res, "")
		}

	case "vault_decrypt":
		res, err := vault.Decrypt(msg.Payload)
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			sendResp(c, "ok", string(res), "")
		}

	case "storage_transfer":
		var params struct {
			SrcURL     string            `json:"src_url"`
			SrcHeaders map[string]string `json:"src_headers"`
			DstURL     string            `json:"dst_url"`
			Method     string            `json:"method"`
			DstHeaders map[string]string `json:"dst_headers"`
		}
		if err := json.Unmarshal([]byte(msg.Payload), &params); err != nil {
			sendResp(c, "fail", nil, "Invalid storage_transfer payload")
			return
		}
		err := storageMgr.TransferStream(context.Background(), params.SrcURL, params.SrcHeaders, params.DstURL, params.Method, params.DstHeaders)
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			sendResp(c, "ok", "Transfer completed", "")
		}

	case "storage_oauth_listen":
		port := 8421
		if msg.Payload != "" {
			fmt.Sscanf(msg.Payload, "%d", &port)
		}
		code, err := storageMgr.StartOAuthListener(port)
		if err != nil {
			sendResp(c, "fail", nil, err.Error())
		} else {
			sendResp(c, "ok", code, "")
		}

	default:
		sendResp(c, "error", nil, "Unknown Command Type: "+msg.Type)
	}
}

func downloadFile(url string, filepath string) error {
	resp, err := http.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	out, err := os.Create(filepath)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, resp.Body)
	return err
}

func sendResp(c *websocket.Conn, status string, data interface{}, errMsg string) {
	resp := Response{
		Status:   status,
		Data:     data,
		Error:    errMsg,
		RunnerID: *runnerID,
	}
	mu.Lock()
	defer mu.Unlock()
	if err := c.WriteJSON(resp); err != nil {
		log.Printf("⚠️ 发送响应失败: %v", err)
	}
}

func sendRespWithID(c *websocket.Conn, status string, data interface{}, errMsg string, requestID string) {
	resp := Response{
		Status:    status,
		Data:      data,
		Error:     errMsg,
		RunnerID:  *runnerID,
		RequestID: requestID,
	}
	mu.Lock()
	defer mu.Unlock()
	if err := c.WriteJSON(resp); err != nil {
		log.Printf("⚠️ 发送响应失败: %v", err)
	}
}
