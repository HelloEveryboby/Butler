// interactive_shell.go — 交互式远程 Shell 模块
//
// 提供真正的 PTY 交互式 Shell 会话，支持持续的双向通信，
// 而非原版的一次性 shell 命令执行。
//
// 新增指令:
//   - shell_session_create : 创建一个新的交互式 Shell 会话，返回 session_id
//   - shell_session_input  : 向指定会话发送输入
//   - shell_session_resize : 调整 PTY 大小
//   - shell_session_close  : 关闭指定会话
//   - shell_session_list   : 列出所有活跃会话

package main

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"
)

// ShellSession 一个交互式 Shell 会话
type ShellSession struct {
	ID        string    `json:"id"`
	PtyFile   *os.File  `json:"-"`
	Cmd       *exec.Cmd `json:"-"`
	CreatedAt time.Time `json:"created_at"`
	Size      struct {
		Rows uint16 `json:"rows"`
		Cols uint16 `json:"cols"`
	} `json:"size"`
	mu         sync.Mutex
	active     bool
	outputChan chan []byte
	done       chan struct{}
}

// InteractiveShellManager 管理多个交互式 Shell 会话
type InteractiveShellManager struct {
	sessions map[string]*ShellSession
	mu       sync.Mutex
}

// NewInteractiveShellManager 创建交互式 Shell 管理器
func NewInteractiveShellManager() *InteractiveShellManager {
	return &InteractiveShellManager{
		sessions: make(map[string]*ShellSession),
	}
}

// CreateSession 创建一个新的交互式 Shell 会话
func (ism *InteractiveShellManager) CreateSession(rows, cols uint16) (*ShellSession, error) {
	ism.mu.Lock()
	defer ism.mu.Unlock()

	sessionID := fmt.Sprintf("shell_%d", time.Now().UnixNano())

	// 根据平台选择默认 Shell
	shell := "/bin/bash"
	if _, err := os.Stat("/bin/zsh"); err == nil {
		shell = "/bin/zsh"
	}

	cmd := exec.Command(shell)
	cmd.Env = os.Environ()

	// 创建 PTY (需要 github.com/creack/pty)
	ptmx, err := ptyStart(cmd)
	if err != nil {
		// PTY 不可用时回退到管道模式
		return nil, fmt.Errorf("failed to start PTY (install creack/pty or build with linux tag): %w", err)
	}

	if rows == 0 {
		rows = 24
	}
	if cols == 0 {
		cols = 80
	}
	ptySetsize(ptmx, rows, cols)

	session := &ShellSession{
		ID:         sessionID,
		PtyFile:    ptmx,
		Cmd:        cmd,
		CreatedAt:  time.Now(),
		active:     true,
		outputChan: make(chan []byte, 4096),
		done:       make(chan struct{}),
	}
	session.Size.Rows = rows
	session.Size.Cols = cols

	go ism.readOutput(session)
	ism.sessions[sessionID] = session

	return session, nil
}

// readOutput 从 PTY 读取输出并推送到 channel
func (ism *InteractiveShellManager) readOutput(session *ShellSession) {
	buf := make([]byte, 4096)
	for {
		n, err := session.PtyFile.Read(buf)
		if n > 0 {
			data := make([]byte, n)
			copy(data, buf[:n])
			select {
			case session.outputChan <- data:
			default:
			}
		}
		if err != nil {
			break
		}
	}
	close(session.done)
	session.mu.Lock()
	session.active = false
	session.mu.Unlock()
}

// WriteInput 向指定会话写入输入
func (ism *InteractiveShellManager) WriteInput(sessionID string, input string) error {
	ism.mu.Lock()
	session, exists := ism.sessions[sessionID]
	ism.mu.Unlock()

	if !exists {
		return fmt.Errorf("session %s not found", sessionID)
	}

	session.mu.Lock()
	defer session.mu.Unlock()
	if !session.active {
		return fmt.Errorf("session %s is not active", sessionID)
	}

	_, err := session.PtyFile.Write([]byte(input))
	return err
}

// Resize 调整指定会话的 PTY 大小
func (ism *InteractiveShellManager) Resize(sessionID string, rows, cols uint16) error {
	ism.mu.Lock()
	session, exists := ism.sessions[sessionID]
	ism.mu.Unlock()

	if !exists {
		return fmt.Errorf("session %s not found", sessionID)
	}

	session.mu.Lock()
	defer session.mu.Unlock()
	if !session.active {
		return fmt.Errorf("session %s is not active", sessionID)
	}

	ptySetsize(session.PtyFile, rows, cols)
	session.Size.Rows = rows
	session.Size.Cols = cols
	return nil
}

// CloseSession 关闭指定会话
func (ism *InteractiveShellManager) CloseSession(sessionID string) error {
	ism.mu.Lock()
	session, exists := ism.sessions[sessionID]
	if exists {
		delete(ism.sessions, sessionID)
	}
	ism.mu.Unlock()

	if !exists {
		return fmt.Errorf("session %s not found", sessionID)
	}

	session.mu.Lock()
	session.active = false
	session.mu.Unlock()

	if session.PtyFile != nil {
		session.PtyFile.Close()
	}
	if session.Cmd.Process != nil {
		session.Cmd.Process.Kill()
		session.Cmd.Wait()
	}

	return nil
}

// ListSessions 列出所有活跃会话
func (ism *InteractiveShellManager) ListSessions() []map[string]interface{} {
	ism.mu.Lock()
	defer ism.mu.Unlock()

	result := make([]map[string]interface{}, 0)
	for id, s := range ism.sessions {
		s.mu.Lock()
		result = append(result, map[string]interface{}{
			"id":         id,
			"active":     s.active,
			"created_at": s.CreatedAt,
			"rows":       s.Size.Rows,
			"cols":       s.Size.Cols,
		})
		s.mu.Unlock()
	}
	return result
}

// GetOutputChan 获取指定会话的输出 channel
func (ism *InteractiveShellManager) GetOutputChan(sessionID string) (<-chan []byte, error) {
	ism.mu.Lock()
	session, exists := ism.sessions[sessionID]
	ism.mu.Unlock()

	if !exists {
		return nil, fmt.Errorf("session %s not found", sessionID)
	}
	return session.outputChan, nil
}

// CloseAll 关闭所有会话
func (ism *InteractiveShellManager) CloseAll() {
	ism.mu.Lock()
	ids := make([]string, 0, len(ism.sessions))
	for id := range ism.sessions {
		ids = append(ids, id)
	}
	ism.mu.Unlock()

	for _, id := range ids {
		ism.CloseSession(id)
	}
}

// HandleShellSessionCommand 处理交互式 Shell 指令（供 runner.go 调用）
func HandleShellSessionCommand(ism *InteractiveShellManager, action string, payload string) (status string, data interface{}, errMsg string) {
	switch action {
	case "shell_session_create":
		session, err := ism.CreateSession(0, 0)
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", map[string]string{
			"session_id": session.ID,
			"message":    "Interactive shell session created",
		}, ""

	case "shell_session_input":
		parts := strings.SplitN(payload, "|", 2)
		if len(parts) < 2 {
			return "fail", nil, "Format: session_id|input_text"
		}
		err := ism.WriteInput(parts[0], parts[1])
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", "Input sent", ""

	case "shell_session_resize":
		parts := strings.SplitN(payload, "|", 3)
		if len(parts) < 3 {
			return "fail", nil, "Format: session_id|rows|cols"
		}
		var rows, cols uint16
		fmt.Sscanf(parts[1], "%d", &rows)
		fmt.Sscanf(parts[2], "%d", &cols)
		err := ism.Resize(parts[0], rows, cols)
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", "Resized", ""

	case "shell_session_close":
		err := ism.CloseSession(payload)
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", "Session closed", ""

	case "shell_session_list":
		sessions := ism.ListSessions()
		return "ok", sessions, ""

	default:
		return "fail", nil, "Unknown shell_session action: " + action
	}
}

// ============================================================
// PTY 兼容层 — 条件编译支持
// Linux/macOS: 使用 creack/pty
// Windows:     使用 conpty (或回退到管道)
// ============================================================

//go:build !windows

import (
	"os/exec"

	"github.com/creack/pty"
)

type ptyWinsize = pty.Winsize

func ptyStart(cmd *exec.Cmd) (*os.File, error) {
	return pty.Start(cmd)
}

func ptySetsize(f *os.File, rows, cols uint16) {
	pty.Setsize(f, &pty.Winsize{Rows: rows, Cols: cols})
}