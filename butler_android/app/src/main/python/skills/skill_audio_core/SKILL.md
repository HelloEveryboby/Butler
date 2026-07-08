---
name: MediaSync Audio Core
description: Real-time system audio capture and FFT spectrum analysis.
triggers:
  - "music sync"
  - "audio spectrum"
  - "spectrum"
provides:
  - "audio.fft_data"
  - "audio.energy"
python_entry: audio_bridge.py
binary_src: audio_capture.go
risk: low
frontend: ui/index.html
---

# MediaSync Audio Core

Provides high-performance audio FFT analysis using a Go-based capture engine.
Outputs data via TLV IPC for UI visualization and STM32 hardware sync.
