// +build !windows

package main

import (
	"os/exec"
	"syscall"
)

func (pm *ProcessManager) applyResourceLimits(cmd *exec.Cmd, risk string) {
	// Linux: Niceness and Cgroups
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setpgid: true,
	}
	// Set Niceness to 19 (lowest priority) if risk is high or low power
	if risk == "high" {
		newArgs := []string{"-n", "19", cmd.Path}
		newArgs = append(newArgs, cmd.Args[1:]...)
		cmd.Path = "/usr/bin/nice"
		cmd.Args = append([]string{"nice"}, newArgs...)
	}
}
