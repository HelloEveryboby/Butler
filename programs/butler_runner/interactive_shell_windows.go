// interactive_shell_windows.go — Windows PTY 兼容层
// Windows 下使用管道模式回退（后续可接入 conpty）

package main

import (
	"fmt"
	"os"
	"os/exec"
)

type ptyWinsize struct {
	Rows uint16
	Cols uint16
}

func ptyStart(cmd *exec.Cmd) (*os.File, error) {
	// Windows 回退: 使用管道而非 PTY
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, err
	}
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}

	if err := cmd.Start(); err != nil {
		return nil, err
	}

	// 返回 stdin 作为写入端
	// 注意: Windows 下此模式为简化实现，完整 PTY 需要 conpty
	go func() {
		buf := make([]byte, 4096)
		for {
			n, _ := stdout.Read(buf)
			if n > 0 {
				// 可以通过回调推送到 WebSocket
				_ = n
			}
		}
	}()
	go func() {
		buf := make([]byte, 4096)
		for {
			n, _ := stderr.Read(buf)
			if n > 0 {
				_ = n
			}
		}
	}()

	// 将 stdin 包装为 *os.File (Unix domain socket 模拟)
	// 实际使用中建议直接暴露 stdin writer
	return nil, fmt.Errorf("Windows PTY not yet implemented, use shell command instead")
}

func ptySetsize(f *os.File, rows, cols uint16) {
	// Windows 下 PTY resize 暂不支持
}