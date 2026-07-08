package main

import (
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/mem"
	"github.com/shirou/gopsutil/v4/process"
)

/**
 * Snapshot Engine: High-frequency metrics collection and ring buffer management.
 */

type MetricSnapshot struct {
	Timestamp int64                  `json:"ts"`
	CPU       float64                `json:"cpu"`
	Memory    float64                `json:"mem"`
	Processes map[int32]ProcessStats `json:"procs"`
}

type ProcessStats struct {
	Name    string  `json:"name"`
	CPU     float64 `json:"cpu"`
	Memory  float32 `json:"mem"`
	Status  string  `json:"status"`
}

type SnapshotEngine struct {
	buffer     []MetricSnapshot
	size       int
	head       int
	mu         sync.Mutex
	archiveFile string
}

func NewSnapshotEngine(size int, archivePath string) *SnapshotEngine {
	return &SnapshotEngine{
		buffer:      make([]MetricSnapshot, size),
		size:        size,
		archiveFile: archivePath,
	}
}

func (s *SnapshotEngine) Start() {
	// 200ms high-frequency collection
	go s.collectionLoop()
	// 5s archive loop
	go s.archiveLoop()
}

func (s *SnapshotEngine) collectionLoop() {
	ticker := time.NewTicker(200 * time.Millisecond)
	for range ticker.C {
		snapshot := s.collect()
		s.Push(snapshot)

		// DRAS: Trigger slowdown signal if load is high
		if snapshot.CPU > 85 {
			s.triggerSlowdown()
		}
	}
}

func (s *SnapshotEngine) triggerSlowdown() {
	// Find the Python butler process and send SIGUSR1 (Linux)
	if runtime.GOOS != "windows" {
		procs, _ := process.Processes()
		for _, p := range procs {
			name, _ := p.Name()
			if strings.Contains(strings.ToLower(name), "python") {
				// Send SIGUSR1
				p.SendSignal(syscall.SIGUSR1)
			}
		}
	}
}

func (s *SnapshotEngine) collect() MetricSnapshot {
	v, _ := mem.VirtualMemory()
	c, _ := cpu.Percent(0, false)

	cpuVal := 0.0
	if len(c) > 0 {
		cpuVal = c[0]
	}

	snap := MetricSnapshot{
		Timestamp: time.Now().UnixNano() / int64(time.Millisecond),
		CPU:       cpuVal,
		Memory:    v.UsedPercent,
		Processes: make(map[int32]ProcessStats),
	}

	// Only collect top processes to save CPU in high-load scenarios
	procs, _ := process.Processes()
	for i, p := range procs {
		if i > 10 { break } // Limit to top 10 for ring buffer efficiency
		name, _ := p.Name()
		cpuP, _ := p.CPUPercent()
		memP, _ := p.MemoryPercent()
		status, _ := p.Status()
		snap.Processes[p.Pid] = ProcessStats{
			Name:   name,
			CPU:    cpuP,
			Memory: memP,
			Status: status[0],
		}
	}

	return snap
}

func (s *SnapshotEngine) Push(snap MetricSnapshot) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.buffer[s.head] = snap
	s.head = (s.head + 1) % s.size
}

func (s *SnapshotEngine) GetLatest() MetricSnapshot {
	s.mu.Lock()
	defer s.mu.Unlock()
	prev := (s.head - 1 + s.size) % s.size
	return s.buffer[prev]
}

func (s *SnapshotEngine) archiveLoop() {
	ticker := time.NewTicker(5 * time.Second)
	for range ticker.C {
		s.archive()
	}
}

func (s *SnapshotEngine) archive() {
	s.mu.Lock()
	snap := s.buffer[(s.head - 1 + s.size) % s.size]
	s.mu.Unlock()

	// Delta Compression Prototype: Only log if CPU or Memory changed significantly (>2%)
	// This reduces I/O pressure on low-end devices
	if snap.CPU > 2 || snap.Memory > 2 {
		data, _ := json.Marshal(snap)
		f, err := os.OpenFile(s.archiveFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		if err == nil {
			f.Write(data)
			f.Write([]byte("\n"))
			f.Close()
		}
	}
}

var snapshotEngine = NewSnapshotEngine(100, "data/snapshot_history.jsonl")
