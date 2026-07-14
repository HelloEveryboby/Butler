// clipboard.go — 跨平台剪贴板同步模块
//
// 提供剪贴板内容读取、写入和变更监听功能。
// 通过 WebSocket 指令与 Butler 主系统双向同步剪贴板。
//
// 支持指令:
//   - clipboard_read   : 读取当前剪贴板内容
//   - clipboard_write  : 写入内容到剪贴板
//   - clipboard_watch  : 启动/停止剪贴板变更监听（自动推送到主系统）
//
// 平台支持:
//   - Linux:   xclip / xsel / wl-copy
//   - macOS:   pbcopy / pbpaste
//   - Windows: PowerShell

package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os/exec"
	"runtime"
	"strings"
	"sync"
	"time"
)

// ClipboardManager 跨平台剪贴板管理器
type ClipboardManager struct {
	mu        sync.Mutex
	lastText  string
	watching  bool
	cancelCtx context.CancelFunc
	onChange  func(text string) // 变更回调，推送到主系统
}

// NewClipboardManager 创建剪贴板管理器
func NewClipboardManager() *ClipboardManager {
	return &ClipboardManager{}
}

// OnChange 设置剪贴板变更回调
func (cm *ClipboardManager) OnChange(fn func(text string)) {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	cm.onChange = fn
}

// Read 读取剪贴板内容
func (cm *ClipboardManager) Read() (string, error) {
	var cmd *exec.Cmd

	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("pbpaste")
	case "windows":
		cmd = exec.Command("powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw")
	default:
		if _, err := exec.LookPath("xclip"); err == nil {
			cmd = exec.Command("xclip", "-selection", "clipboard", "-o")
		} else if _, err := exec.LookPath("xsel"); err == nil {
			cmd = exec.Command("xsel", "--clipboard", "--output")
		} else if _, err := exec.LookPath("wl-paste"); err == nil {
			cmd = exec.Command("wl-paste")
		} else {
			return "", fmt.Errorf("no clipboard tool found (install xclip or xsel)")
		}
	}

	output, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("clipboard read failed: %w", err)
	}

	text := strings.TrimSpace(string(output))
	cm.mu.Lock()
	cm.lastText = text
	cm.mu.Unlock()

	return text, nil
}

// Write 写入内容到剪贴板
func (cm *ClipboardManager) Write(text string) error {
	var cmd *exec.Cmd

	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("pbcopy")
	case "windows":
		cmd = exec.Command("powershell", "-NoProfile", "-Command",
			"Set-Clipboard -Value '"+escapePS(text)+"'")
	default:
		if _, err := exec.LookPath("xclip"); err == nil {
			cmd = exec.Command("xclip", "-selection", "clipboard")
		} else if _, err := exec.LookPath("xsel"); err == nil {
			cmd = exec.Command("xsel", "--clipboard", "--input")
		} else if _, err := exec.LookPath("wl-copy"); err == nil {
			cmd = exec.Command("wl-copy")
		} else {
			return fmt.Errorf("no clipboard tool found (install xclip or xsel)")
		}
	}

	cmd.Stdin = strings.NewReader(text)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("clipboard write failed: %w", err)
	}

	cm.mu.Lock()
	cm.lastText = text
	cm.mu.Unlock()

	return nil
}

// Watch 启动剪贴板变更监听（轮询模式，500ms 间隔）
func (cm *ClipboardManager) Watch(ctx context.Context) {
	cm.mu.Lock()
	if cm.watching {
		cm.mu.Unlock()
		return
	}
	cm.watching = true
	childCtx, cancel := context.WithCancel(ctx)
	cm.cancelCtx = cancel
	onChange := cm.onChange
	cm.mu.Unlock()

	initial, _ := cm.Read()

	ticker := time.NewTicker(500 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-childCtx.Done():
			cm.mu.Lock()
			cm.watching = false
			cm.mu.Unlock()
			return
		case <-ticker.C:
			current, err := cm.Read()
			if err != nil {
				continue
			}
			if current != initial && current != "" {
				initial = current
				cm.mu.Lock()
				fn := onChange
				cm.mu.Unlock()
				if fn != nil {
					fn(current)
				}
			}
		}
	}
}

// StopWatch 停止剪贴板监听
func (cm *ClipboardManager) StopWatch() {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	if cm.cancelCtx != nil {
		cm.cancelCtx()
		cm.cancelCtx = nil
	}
	cm.watching = false
}

// IsWatching 返回是否正在监听
func (cm *ClipboardManager) IsWatching() bool {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	return cm.watching
}

// GetLastText 获取上次读取的剪贴板内容
func (cm *ClipboardManager) GetLastText() string {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	return cm.lastText
}

// escapePS 转义 PowerShell 特殊字符
func escapePS(s string) string {
	s = strings.ReplaceAll(s, "'", "''")
	return s
}

// HandleClipboardCommand 处理剪贴板相关指令（供 runner.go 调用）
func HandleClipboardCommand(cm *ClipboardManager, action string, payload string) (status string, data interface{}, errMsg string) {
	switch action {
	case "clipboard_read":
		text, err := cm.Read()
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", map[string]string{"text": text, "length": fmt.Sprintf("%d", len(text))}, ""

	case "clipboard_write":
		err := cm.Write(payload)
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", "Clipboard updated", ""

	case "clipboard_watch":
		if payload == "stop" {
			cm.StopWatch()
			return "ok", "Clipboard watching stopped", ""
		}
		if cm.IsWatching() {
			return "ok", "Already watching", ""
		}
		go cm.Watch(context.Background())
		return "ok", "Clipboard watching started (500ms poll)", ""

	default:
		return "fail", nil, "Unknown clipboard action: " + action
	}
}

// detectPlatformClipboard 检测平台剪贴板工具可用性
func detectPlatformClipboard() map[string]interface{} {
	info := map[string]interface{}{
		"os":    runtime.GOOS,
		"tools": []string{},
	}

	switch runtime.GOOS {
	case "darwin":
		info["tools"] = []string{"pbcopy", "pbpaste"}
		info["native"] = true
	case "windows":
		info["tools"] = []string{"powershell"}
		info["native"] = true
	default:
		tools := []string{}
		if _, err := exec.LookPath("xclip"); err == nil {
			tools = append(tools, "xclip")
		}
		if _, err := exec.LookPath("xsel"); err == nil {
			tools = append(tools, "xsel")
		}
		if _, err := exec.LookPath("wl-copy"); err == nil {
			tools = append(tools, "wl-copy", "wl-paste")
		}
		info["tools"] = tools
		info["native"] = len(tools) > 0
	}

	return info
}

// ============================================================
// StreamLogger — 修复原版 io.Discard 丢弃子进程输出的缺陷
// 捕获子进程 stdout/stderr 并通过 WebSocket 流式推送到主系统
// ============================================================

// StreamLine 代表一行子进程输出
type StreamLine struct {
	Source  string `json:"source"`  // "stdout" or "stderr"
	Line    string `json:"line"`
	SkillID string `json:"skill_id"`
	Time    int64  `json:"time"`
}

// StreamLogger 管理子进程输出流
type StreamLogger struct {
	outputChan chan StreamLine
	done       chan struct{}
}

// NewStreamLogger 创建流式日志管理器
func NewStreamLogger(bufferSize int) *StreamLogger {
	return &StreamLogger{
		outputChan: make(chan StreamLine, bufferSize),
		done:       make(chan struct{}),
	}
}

// StartReading 开始从 pipe 逐行读取输出
func (sl *StreamLogger) StartReading(pipe io.ReadCloser, source string, skillID string) {
	scanner := bufio.NewScanner(pipe)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)

	go func() {
		defer close(sl.done)
		for scanner.Scan() {
			line := scanner.Text()
			select {
			case sl.outputChan <- StreamLine{
				Source:  source,
				Line:    line,
				SkillID: skillID,
				Time:    time.Now().UnixNano() / int64(time.Millisecond),
			}:
			default:
				<-sl.outputChan
				sl.outputChan <- StreamLine{
					Source:  source,
					Line:    "[TRUNCATED] " + line,
					SkillID: skillID,
					Time:    time.Now().UnixNano() / int64(time.Millisecond),
				}
			}
		}
	}()
}

// OutputChan 返回输出通道
func (sl *StreamLogger) OutputChan() <-chan StreamLine {
	return sl.outputChan
}

// Close 关闭日志管理器
func (sl *StreamLogger) Close() {
	close(sl.outputChan)
}