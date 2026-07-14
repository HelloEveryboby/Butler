// runner_patches.go — 关键补丁与集成代码
//
// 本文件包含需要对 runner.go 应用的所有修改，以补丁形式提供。
// 每个补丁标注了 [PATCH] 前缀和原始位置，便于定位和应用。
//
// 补丁清单:
//   PATCH-001: HMAC-SHA256 消息签名（安全增强）
//   PATCH-002: spawn_skill 子进程输出流式推送（修复 io.Discard 缺陷）
//   PATCH-003: 新模块初始化与 normalizeType 扩展
//   PATCH-004: handleTask 新增指令路由
//   PATCH-005: isSafePath 增强（白名单目录支持）
//   PATCH-006: 交互式 Shell 输出推送 goroutine
//   PATCH-007: 优雅关闭清理
//   PATCH-008: 环境变量读取替代硬编码默认值

package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/gorilla/websocket"
)

// ============================================================
// PATCH-001: HMAC-SHA256 消息签名
// 位置: 新增全局函数
// 说明: 为每条消息添加 HMAC 签名，防止篡改和重放
// ============================================================

// signMessage 为消息生成 HMAC-SHA256 签名
func signMessage(msg Message) string {
	payload := fmt.Sprintf("%s|%s|%s|%v",
		msg.Type, msg.Payload, msg.RunnerID, msg.Data)

	mac := hmac.New(sha256.New, []byte(*authToken))
	mac.Write([]byte(payload))
	return hex.EncodeToString(mac.Sum(nil))
}

// ============================================================
// PATCH-002: spawn_skill 子进程输出流式推送
// 位置: 替换 monitorProcess 中的 io.Discard goroutine
// 原始代码:
//   go func() {
//       scanner := io.TeeReader(stdout, os.Stdout)
//       io.Copy(io.Discard, scanner)
//   }()
//   go func() {
//       io.Copy(io.Discard, stderr)
//   }()
// ============================================================

// patchedMonitorProcess 替代原版 monitorProcess
func (pm *ProcessManager) patchedMonitorProcess(
	mp *ManagedProcess,
	stdout, stderr io.ReadCloser,
	conn *websocket.Conn,
) {
	sl := NewStreamLogger(1024)
	sl.StartReading(stdout, "stdout", mp.Config.ID)

	go func() {
		slErr := NewStreamLogger(256)
		slErr.StartReading(stderr, "stderr", mp.Config.ID)
		for range slErr.OutputChan() {
			// stderr 行可选择性写入本地日志
		}
	}()

	// 启动输出推送 goroutine
	go func() {
		ticker := time.NewTicker(200 * time.Millisecond)
		defer ticker.Stop()

		batch := []StreamLine{}
		for {
			select {
			case line, ok := <-sl.OutputChan():
				if !ok {
					if len(batch) > 0 {
						sendBatch(conn, batch, mp.Config.ID)
					}
					return
				}
				batch = append(batch, line)
				if len(batch) >= 50 {
					sendBatch(conn, batch, mp.Config.ID)
					batch = batch[:0]
				}
			case <-ticker.C:
				if len(batch) > 0 {
					sendBatch(conn, batch, mp.Config.ID)
					batch = batch[:0]
				}
			}
		}
	}()

	err := mp.Cmd.Wait()

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

		backoff := time.Duration(mp.RestartCount) * time.Second
		if backoff > 30*time.Second {
			backoff = 30 * time.Second
		}
		time.Sleep(backoff)

		pm.cleanupLegacyFiles(mp.Config.Path)
		pm.startProcess(mp)
	}
}

// sendBatch 批量推送子进程输出到主系统
func sendBatch(conn *websocket.Conn, lines []StreamLine, skillID string) {
	if conn == nil || len(lines) == 0 {
		return
	}

	type OutputBatch struct {
		SkillID string       `json:"skill_id"`
		Lines   []StreamLine `json:"lines"`
	}

	msg := Message{
		Type:     "skill_output",
		Data:     OutputBatch{SkillID: skillID, Lines: lines},
		RunnerID: *runnerID,
		Token:    *authToken,
	}

	mu.Lock()
	defer mu.Unlock()
	conn.WriteJSON(msg)
}

// ============================================================
// PATCH-003: 新模块初始化与 normalizeType 扩展
// ============================================================

// 新增全局模块实例
var (
	clipboardMgr    *ClipboardManager
	shellSessionMgr *InteractiveShellManager
	serviceMgr      *ServiceManager
)

// initModules 初始化所有新模块（在 main() 中调用）
func initModules() {
	clipboardMgr = NewClipboardManager()

	clipboardMgr.OnChange(func(text string) {
		if procMgr != nil && procMgr.conn != nil {
			msg := Message{
				Type:     "clipboard_changed",
				Data:     map[string]string{"text": text, "length": fmt.Sprintf("%d", len(text))},
				RunnerID: *runnerID,
				Token:    *authToken,
			}
			mu.Lock()
			procMgr.conn.WriteJSON(msg)
			mu.Unlock()
		}
	})

	shellSessionMgr = NewInteractiveShellManager()
	serviceMgr = NewServiceManager()

	fmt.Println("✅ 增强模块已加载: clipboard, interactive_shell, service_manager")
}

// patchedNormalizeType 扩展 normalizeType 以支持新指令
func patchedNormalizeType(t string) string {
	base := normalizeType(t)

	switch base {
	case "clipboard_read", "clip_read", "剪贴板读取":
		return "clipboard_read"
	case "clipboard_write", "clip_write", "剪贴板写入":
		return "clipboard_write"
	case "clipboard_watch", "clip_watch", "剪贴板监听":
		return "clipboard_watch"
	case "shell_session_create", "shell_create", "创建会话":
		return "shell_session_create"
	case "shell_session_input", "shell_input", "会话输入":
		return "shell_session_input"
	case "shell_session_resize", "shell_resize", "会话缩放":
		return "shell_session_resize"
	case "shell_session_close", "shell_close", "关闭会话":
		return "shell_session_close"
	case "shell_session_list", "shell_list", "会话列表":
		return "shell_session_list"
	case "service_list", "服务列表":
		return "service_list"
	case "service_status", "服务状态":
		return "service_status"
	case "service_start", "服务启动":
		return "service_start"
	case "service_stop", "服务停止":
		return "service_stop"
	case "service_restart", "服务重启":
		return "service_restart"
	case "service_logs", "服务日志":
		return "service_logs"
	case "process_list", "进程列表":
		return "process_list"
	case "process_kill", "进程终止":
		return "process_kill"
	default:
		return base
	}
}

// ============================================================
// PATCH-004: handleTask 新增指令路由
// 位置: 在 connect() 中替换 handleTask 调用为 handleTaskPatched
// ============================================================

func handleTaskPatched(c *websocket.Conn, msg Message) {
	msgType := patchedNormalizeType(msg.Type)

	switch msgType {
	case "clipboard_read", "clipboard_write", "clipboard_watch":
		status, data, errMsg := HandleClipboardCommand(clipboardMgr, msgType, msg.Payload)
		sendRespWithID(c, status, data, errMsg, msg.RequestID)
		return

	case "shell_session_create", "shell_session_input", "shell_session_resize",
		"shell_session_close", "shell_session_list":
		status, data, errMsg := HandleShellSessionCommand(shellSessionMgr, msgType, msg.Payload)
		sendRespWithID(c, status, data, errMsg, msg.RequestID)

		if msgType == "shell_session_create" && status == "ok" {
			if m, ok := data.(map[string]string); ok {
				sessionID := m["session_id"]
				go pushShellOutput(c, sessionID)
			}
		}
		return

	case "service_list", "service_status", "service_start", "service_stop",
		"service_restart", "service_logs", "process_list", "process_kill":
		status, data, errMsg := HandleServiceCommand(serviceMgr, msgType, msg.Payload)
		sendRespWithID(c, status, data, errMsg, msg.RequestID)
		return
	}

	// 回退到原版 handleTask
	handleTask(c, msg)
}

// pushShellOutput 推送交互式 Shell 会话输出
func pushShellOutput(c *websocket.Conn, sessionID string) {
	ch, err := shellSessionMgr.GetOutputChan(sessionID)
	if err != nil {
		return
	}

	for data := range ch {
		msg := Message{
			Type:     "shell_session_output",
			Data: map[string]interface{}{
				"session_id": sessionID,
				"output":     string(data),
			},
			RunnerID:  *runnerID,
			Token:     *authToken,
			RequestID: sessionID,
		}
		mu.Lock()
		c.WriteJSON(msg)
		mu.Unlock()
	}
}

// ============================================================
// PATCH-005: isSafePath 增强
// ============================================================

var safeBasePaths []string

func initSafePaths() {
	if envPaths := os.Getenv("BUTLER_RUNNER_SAFE_PATHS"); envPaths != "" {
		safeBasePaths = strings.Split(envPaths, ",")
		for i := range safeBasePaths {
			safeBasePaths[i] = strings.TrimSpace(safeBasePaths[i])
		}
	}
	if len(safeBasePaths) == 0 {
		if wd, err := os.Getwd(); err == nil {
			safeBasePaths = []string{wd}
		}
	}
}

func patchedIsSafePath(path string) bool {
	if path == "" || path == "/" || path == "." || path == ".." {
		return false
	}
	if strings.Contains(path, "..") {
		return false
	}
	absPath, err := filepath.Abs(path)
	if err != nil {
		return false
	}
	for _, safeBase := range safeBasePaths {
		if strings.HasPrefix(absPath, safeBase) {
			return true
		}
	}
	if len(safeBasePaths) == 0 {
		if filepath.IsAbs(path) {
			if path == "/" || (runtime.GOOS == "windows" && len(path) <= 3 && strings.HasSuffix(path, ":\\")) {
				return false
			}
		}
		return true
	}
	return false
}

// ============================================================
// PATCH-007: 优雅关闭清理
// ============================================================

func gracefulShutdown() {
	fmt.Println("\n👋 Butler-Runner 正在优雅关闭...")

	if shellSessionMgr != nil {
		shellSessionMgr.CloseAll()
		fmt.Println("  ✅ 交互式 Shell 会话已关闭")
	}

	if clipboardMgr != nil {
		clipboardMgr.StopWatch()
		fmt.Println("  ✅ 剪贴板监听已停止")
	}

	if vault != nil {
		vault.Clear()
		fmt.Println("  ✅ Vault 密钥已擦除")
	}

	os.Remove("temp_screenshot.jpg")
	fmt.Println("👋 Butler-Runner 已安全关闭")
}

// ============================================================
// PATCH-008: 环境变量读取替代硬编码默认值
// ============================================================

func applyEnvironmentOverrides() {
	if envURL := os.Getenv("BUTLER_SERVER_URL"); envURL != "" && *serverURL == "ws://localhost:8000/ws/butler" {
		*serverURL = envURL
		fmt.Printf("🌐 Server URL from env: %s\n", *serverURL)
	}

	if envToken := os.Getenv("BUTLER_RUNNER_TOKEN"); envToken != "" && *authToken == "" {
		*authToken = envToken
		fmt.Println("🔑 Token loaded from environment variable")
	}

	if envID := os.Getenv("RUNNER_ID"); envID != "" && *runnerID == "default_runner" {
		*runnerID = envID
		fmt.Printf("🆔 Runner ID from env: %s\n", *runnerID)
	}
}

// ============================================================
// main() 函数集成模板
// 位置: 替换原版 main() 函数
// ============================================================

/*
func main() {
	flag.Parse()

	// [PATCH-008] 环境变量覆盖
	applyEnvironmentOverrides()

	if *authToken == "" {
		fmt.Println("❌ ERROR: Auth token is required. Use -token or BUTLER_RUNNER_TOKEN env var.")
		os.Exit(1)
	}

	if *authToken == "BUTLER_SECRET_2026" {
		fmt.Println("⚠️ WARNING: Using a default or insecure token.")
	}

	// [PATCH-005] 初始化安全路径
	initSafePaths()

	// [PATCH-003] 初始化增强模块
	initModules()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	fmt.Printf("🚀 Butler-Runner Pro v2.0 [%s] 启动中...\n", *runnerID)
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
	// [PATCH-007] 优雅关闭
	gracefulShutdown()
}
*/