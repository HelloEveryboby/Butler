package main

import (
	"fmt"
	"syscall"
	"unsafe"
)

// PinMemory locks the underlying memory of the byte slice.
func (v *VaultEngine) pinMemory(data []byte) error {
	if len(data) == 0 {
		return nil
	}

	ptr := uintptr(unsafe.Pointer(&data[0]))
	size := uintptr(len(data))

	// Windows: VirtualLock
	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	vLock := kernel32.NewProc("VirtualLock")
	ret, _, err := vLock.Call(ptr, size)
	if ret == 0 {
		return fmt.Errorf("VirtualLock failed: %v", err)
	}

	v.pinned = true
	return nil
}

// UnpinMemory unlocks the memory.
func (v *VaultEngine) unpinMemory(data []byte) error {
	if !v.pinned {
		return nil
	}

	ptr := uintptr(unsafe.Pointer(&data[0]))
	size := uintptr(len(data))

	kernel32 := syscall.NewLazyDLL("kernel32.dll")
	vUnlock := kernel32.NewProc("VirtualUnlock")
	vUnlock.Call(ptr, size)

	v.pinned = false
	return nil
}
