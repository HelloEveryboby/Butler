// service_manager.go — 系统服务管理模块
//
// 提供远程系统服务（Windows Services / Linux systemd / macOS launchd）的
// 查询、启动、停止、重启和状态监控功能。
//
// 新增指令:
//   - service_list     : 列出系统服务
//   - service_status   : 查询指定服务状态
//   - service_start    : 启动服务
//   - service_stop     : 停止服务
//   - service_restart  : 重启服务
//   - service_logs     : 获取服务最近日志
//   - process_list     : 列出运行中的进程（增强版 sys_info）
//   - process_kill     : 终止指定 PID

package main

import (
	"fmt"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/shirou/gopsutil/v4/process"
)

// ServiceInfo 系统服务信息
type ServiceInfo struct {
	Name        string `json:"name"`
	DisplayName string `json:"display_name"`
	Status      string `json:"status"`
}

// ProcessInfoEnhanced 增强版进程信息
type ProcessInfoEnhanced struct {
	PID       int32   `json:"pid"`
	Name      string  `json:"name"`
	CPU       float64 `json:"cpu"`
	Memory    float32 `json:"memory_mb"`
	MemoryPct float32 `json:"memory_pct"`
	Status    string  `json:"status"`
	Cmdline   string  `json:"cmdline,omitempty"`
	StartedAt string  `json:"started_at,omitempty"`
}

// ServiceManager 系统服务管理器
type ServiceManager struct{}

// NewServiceManager 创建服务管理器
func NewServiceManager() *ServiceManager {
	return &ServiceManager{}
}

// ListServices 列出系统服务
func (sm *ServiceManager) ListServices(filter string) ([]ServiceInfo, error) {
	switch runtime.GOOS {
	case "windows":
		return sm.listServicesWindows(filter)
	default:
		return sm.listServicesUnix(filter)
	}
}

func (sm *ServiceManager) listServicesWindows(filter string) ([]ServiceInfo, error) {
	output, err := exec.Command("powershell", "-NoProfile", "-Command",
		"Get-Service | Select-Object Name,DisplayName,Status | ConvertTo-Json -Compress",
	).Output()
	if err != nil {
		return nil, fmt.Errorf("failed to list services: %w", err)
	}

	var services []ServiceInfo
	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		svc := ServiceInfo{}
		extractField(line, "Name", &svc.Name)
		extractField(line, "DisplayName", &svc.DisplayName)
		if svc.Name != "" {
			services = append(services, svc)
		}
	}

	if filter != "" {
		filtered := []ServiceInfo{}
		for _, s := range services {
			if strings.Contains(strings.ToLower(s.Name), strings.ToLower(filter)) ||
				strings.Contains(strings.ToLower(s.DisplayName), strings.ToLower(filter)) {
				filtered = append(filtered, s)
			}
		}
		return filtered, nil
	}

	return services, nil
}

func (sm *ServiceManager) listServicesUnix(filter string) ([]ServiceInfo, error) {
	cmd := "systemctl"
	if _, err := exec.LookPath(cmd); err != nil {
		cmd = "service"
	}

	var args []string
	if cmd == "systemctl" {
		args = []string{"list-units", "--type=service", "--no-pager", "--plain", "--no-legend"}
	} else {
		args = []string{"--status-all"}
	}

	output, err := exec.Command(cmd, args...).Output()
	if err != nil {
		return nil, fmt.Errorf("failed to list services: %w", err)
	}

	var services []ServiceInfo
	for _, line := range strings.Split(string(output), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}

		svc := ServiceInfo{}
		if cmd == "systemctl" {
			svc.Name = fields[0]
			if len(fields) > 2 {
				svc.Status = normalizeServiceStatus(fields[2])
			}
			if len(fields) > 3 {
				svc.DisplayName = strings.Join(fields[3:], " ")
			}
		} else {
			svc.Name = fields[len(fields)-1]
			svc.Status = normalizeServiceStatus(fields[0])
			svc.DisplayName = svc.Name
		}

		services = append(services, svc)
	}

	if filter != "" {
		filtered := []ServiceInfo{}
		for _, s := range services {
			if strings.Contains(strings.ToLower(s.Name), strings.ToLower(filter)) ||
				strings.Contains(strings.ToLower(s.DisplayName), strings.ToLower(filter)) {
				filtered = append(filtered, s)
			}
		}
		return filtered, nil
	}

	return services, nil
}

// ControlService 控制服务（start/stop/restart）
func (sm *ServiceManager) ControlService(name, action string) (string, error) {
	var cmd *exec.Cmd

	switch runtime.GOOS {
	case "windows":
		switch action {
		case "start":
			cmd = exec.Command("powershell", "-NoProfile", "-Command",
				fmt.Sprintf("Start-Service -Name '%s'", name))
		case "stop":
			cmd = exec.Command("powershell", "-NoProfile", "-Command",
				fmt.Sprintf("Stop-Service -Name '%s' -Force", name))
		default: // restart
			cmd = exec.Command("powershell", "-NoProfile", "-Command",
				fmt.Sprintf("Restart-Service -Name '%s' -Force", name))
		}
	default:
		cmd = exec.Command("sudo", "systemctl", action, name)
	}

	output, err := cmd.CombinedOutput()
	if err != nil {
		return string(output), fmt.Errorf("service %s %s failed: %w", name, action, err)
	}
	return string(output), nil
}

// GetServiceStatus 获取指定服务状态
func (sm *ServiceManager) GetServiceStatus(name string) (*ServiceInfo, error) {
	services, err := sm.ListServices(name)
	if err != nil {
		return nil, err
	}
	for _, s := range services {
		if s.Name == name || strings.Contains(s.Name, name) {
			return &s, nil
		}
	}
	return nil, fmt.Errorf("service %s not found", name)
}

// GetServiceLogs 获取服务最近日志
func (sm *ServiceManager) GetServiceLogs(name string, lines int) (string, error) {
	if lines <= 0 {
		lines = 50
	}

	switch runtime.GOOS {
	case "windows":
		output, err := exec.Command("powershell", "-NoProfile", "-Command",
			fmt.Sprintf("Get-WinEvent -LogName System -ProviderName '%s' -MaxEvents %d | Format-Table TimeCreated,Message -Wrap",
				name, lines),
		).CombinedOutput()
		if err != nil {
			return "", fmt.Errorf("failed to get logs: %w", err)
		}
		return string(output), nil
	default:
		output, err := exec.Command("journalctl", "-u", name, "-n", strconv.Itoa(lines), "--no-pager").CombinedOutput()
		if err != nil {
			return "", fmt.Errorf("failed to get logs: %w", err)
		}
		return string(output), nil
	}
}

// ListProcessesEnhanced 增强版进程列表
func (sm *ServiceManager) ListProcessesEnhanced(filter string) ([]ProcessInfoEnhanced, error) {
	procs, err := process.Processes()
	if err != nil {
		return nil, fmt.Errorf("failed to list processes: %w", err)
	}

	var result []ProcessInfoEnhanced
	for _, p := range procs {
		name, _ := p.Name()
		cpuP, _ := p.CPUPercent()
		memP, _ := p.MemoryPercent()
		memMB := float32(0)

		memInfo, err := p.MemoryInfo()
		if err == nil && memInfo != nil {
			memMB = float32(float64(memInfo.RSS) / 1024.0 / 1024.0)
		}

		cmdline := ""
		if cmdSlice, err := p.CmdlineSlice(); err == nil {
			cmdline = strings.Join(cmdSlice, " ")
		}

		statusArr, _ := p.Status()
		statusStr := "unknown"
		if len(statusArr) > 0 {
			statusStr = statusArr[0]
		}

		createTime, _ := p.CreateTime()
		startedAt := ""
		if createTime > 0 {
			startedAt = time.Unix(0, createTime*int64(time.Millisecond)).Format(time.RFC3339)
		}

		info := ProcessInfoEnhanced{
			PID:       p.Pid,
			Name:      name,
			CPU:       cpuP,
			Memory:    memMB,
			MemoryPct: memP,
			Status:    statusStr,
			Cmdline:   cmdline,
			StartedAt: startedAt,
		}

		if filter != "" {
			if !strings.Contains(strings.ToLower(name), strings.ToLower(filter)) {
				continue
			}
		}

		result = append(result, info)
	}

	return result, nil
}

// KillProcess 终止指定 PID
func (sm *ServiceManager) KillProcess(pid int32, force bool) error {
	p, err := process.NewProcess(pid)
	if err != nil {
		return fmt.Errorf("process %d not found: %w", pid, err)
	}

	if force {
		return p.Kill()
	}
	return p.Terminate()
}

// HandleServiceCommand 处理服务管理指令（供 runner.go 调用）
func HandleServiceCommand(sm *ServiceManager, action string, payload string) (status string, data interface{}, errMsg string) {
	switch action {
	case "service_list":
		services, err := sm.ListServices(payload)
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", services, ""

	case "service_status":
		info, err := sm.GetServiceStatus(payload)
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", info, ""

	case "service_start", "service_stop", "service_restart":
		ctrlAction := strings.TrimPrefix(action, "service_")
		output, err := sm.ControlService(payload, ctrlAction)
		if err != nil {
			return "fail", output, err.Error()
		}
		return "ok", map[string]string{"output": output}, ""

	case "service_logs":
		parts := strings.SplitN(payload, "|", 2)
		lines := 50
		if len(parts) == 2 {
			fmt.Sscanf(parts[1], "%d", &lines)
		}
		logs, err := sm.GetServiceLogs(parts[0], lines)
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", logs, ""

	case "process_list":
		procs, err := sm.ListProcessesEnhanced(payload)
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", procs, ""

	case "process_kill":
		parts := strings.SplitN(payload, "|", 2)
		pid, err := strconv.ParseInt(parts[0], 10, 32)
		if err != nil {
			return "fail", nil, "Invalid PID: " + parts[0]
		}
		force := len(parts) == 2 && parts[1] == "force"
		err = sm.KillProcess(int32(pid), force)
		if err != nil {
			return "fail", nil, err.Error()
		}
		return "ok", fmt.Sprintf("Process %d terminated", pid), ""

	default:
		return "fail", nil, "Unknown service action: " + action
	}
}

// --- Helper functions ---

func normalizeServiceStatus(s string) string {
	s = strings.ToLower(strings.TrimSpace(s))
	switch s {
	case "running", "active", "started", "listening":
		return "running"
	case "stopped", "inactive", "dead", "exited":
		return "stopped"
	case "failed":
		return "failed"
	default:
		return "unknown"
	}
}

func extractField(jsonLine, field string, target *string) bool {
	idx := strings.Index(jsonLine, `"`+field+`":`)
	if idx == -1 {
		return false
	}
	rest := jsonLine[idx+len(field)+4:]
	endQuote := strings.Index(rest, `"`)
	if endQuote == -1 {
		return false
	}
	*target = rest[:endQuote]
	return true
}