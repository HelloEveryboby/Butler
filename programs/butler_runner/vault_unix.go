package main

import (
	"fmt"
	"runtime"
	"syscall"
)

// PinMemory locks the underlying memory of the byte slice.
func (v *VaultEngine) pinMemory(data []byte) error {
	if len(data) == 0 {
		return nil
	}

	if runtime.GOOS == "windows" {
		// This should not be called in Unix build but added for completeness if build tags are not used
		return fmt.Errorf("Windows pinning not supported in Unix build")
	} else {
		// Linux/POSIX: mlock
		err := syscall.Mlock(data)
		if err != nil {
			return fmt.Errorf("mlock failed: %v", err)
		}
	}
	v.pinned = true
	return nil
}

// UnpinMemory unlocks the memory.
func (v *VaultEngine) unpinMemory(data []byte) error {
	if !v.pinned {
		return nil
	}

	if runtime.GOOS == "windows" {
		return nil
	} else {
		syscall.Munlock(data)
	}
	v.pinned = false
	return nil
}
