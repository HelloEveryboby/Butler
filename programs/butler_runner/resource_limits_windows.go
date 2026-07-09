// +build windows

package main

import (
	"os/exec"
	"syscall"
)

func (pm *ProcessManager) applyResourceLimits(cmd *exec.Cmd, risk string) {
	// Windows: Job Objects (Partial Implementation via SysProcAttr)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		CreationFlags: syscall.CREATE_NEW_PROCESS_GROUP | 0x00000008, // DETACHED_PROCESS
	}
}
