package main

import (
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
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"github.com/go-vgo/robotgo"
	"github.com/gorilla/websocket"
	"github.com/vova616/screenshot"
)

// --- 协议定义 ---
type Message struct {
	Type    string `json:"type"`    // cmd, shell, file_ls, screenshot, input, sys_info, ping, pong, register, sleep
	Payload string `json:"payload"` // 指令内容或路径
	Token   string `json:"token"`
	RunnerID string `json:"runner_id,omitempty"`
}

type Response struct {
	Status   string      `json:"status"`
	Data     interface{} `json:"data,omitempty"`
	Error    string      `json:"error,omitempty"`
	RunnerID string      `json:"runner_id"`
}

var (
	serverURL = flag.String("server", "ws://localhost:8000/ws/butler", "Butler server WebSocket URL")
	authToken = flag.String("token", "", "Authentication token (REQUIRED)")
	runnerID  = flag.String("id", "default_runner", "Unique ID for this runner")
	isSleeping = false
	mu        sync.Mutex
)

func main() {
	flag.Parse()

	if *authToken == "" {
		fmt.Println("❌ ERROR: Auth token is required. Use -token to specify it.")
		os.Exit(1)
	}

	if *authToken == "BUTLER_SECRET_2026" {
		fmt.Println("⚠️ WARNING: Using a default or insecure token. Please change it for production use.")
	}

	fmt.Printf("🚀 Butler-Runner Pro [%s] 启动中...\n", *runnerID)
	fmt.Printf("🔗 连接至: %s\n", *serverURL)

	for {
		if err := connect(); err != nil {
			log.Printf("❌ 连接失败: %v, 5秒后重连...", err)
			time.Sleep(5 * time.Second)
			continue
		}
	}
}

func connect() error {
	c, _, err := websocket.DefaultDialer.Dial(*serverURL, nil)
	if err != nil {
		return err
	}
	defer c.Close()
	fmt.Println("✅ 已成功连接至 Butler 主系统")

	// 发送注册消息
	regMsg := Message{
		Type:     "register",
		Token:    *authToken,
		RunnerID: *runnerID,
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

		// 核心指令分发
		go handleTask(c, msg)
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
	default:
		return t
	}
}

func isSafePath(path string) bool {
	if path == "" || path == "/" || path == "." || path == ".." {
		return false
	}

	// Clean the path to resolve any "." or ".."
	cleanPath := filepath.Clean(path)

	// Check for path traversal after cleaning
	if strings.HasPrefix(cleanPath, "..") || strings.Contains(cleanPath, filepath.FromSlash("/../")) {
		return false
	}

	// Check for absolute path in Unix or root in Windows
	if filepath.IsAbs(cleanPath) {
		// Block access to system roots
		if cleanPath == "/" || (runtime.GOOS == "windows" && len(cleanPath) <= 3 && strings.Contains(cleanPath, ":")) {
			return false
		}
		// Block access to sensitive unix directories
		if runtime.GOOS != "windows" {
			sensitive := []string{"/etc", "/root", "/var", "/bin", "/sbin", "/proc", "/sys", "/dev"}
			for _, s := range sensitive {
				if cleanPath == s || strings.HasPrefix(cleanPath, s+"/") {
					return false
				}
			}
		}
	}
	return true
}

func handleTask(c *websocket.Conn, msg Message) {
	msgType := normalizeType(msg.Type)
	switch msgType {
	case "ping":
		sendResp(c, "pong", "alive", "")

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

	case "shell":
		fmt.Printf("⚠️  Executing Shell Command: %s\n", msg.Payload)
		var cmd *exec.Cmd
		if runtime.GOOS == "windows" {
			cmd = exec.Command("cmd", "/C", msg.Payload)
		} else {
			cmd = exec.Command("sh", "-c", msg.Payload)
		}
		output, err := cmd.CombinedOutput()
		if err != nil {
			sendResp(c, "fail", string(output), err.Error())
		} else {
			sendResp(c, "ok", string(output), "")
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
		info := map[string]interface{}{
			"os":      runtime.GOOS,
			"arch":    runtime.GOARCH,
			"cpus":    runtime.NumCPU(),
			"version": robotgo.GetVersion(),
		}
		sendResp(c, "sys", info, "")

	case "sleep":
		mu.Lock()
		isSleeping = true
		mu.Unlock()
		fmt.Println("💤 进入睡眠模式...")
		sendResp(c, "ok", "Runner is now sleeping", "")

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
