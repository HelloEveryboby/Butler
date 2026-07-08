---
name: SecRadar
description: High-concurrency SYN port scanner with Token Bucket rate limiting.
triggers:
  - "scan network"
  - "security scan"
provides:
  - "net.scan_results"
python_entry: sec_manager.py
binary_src: syn_scanner.go
risk: high
---

# SecRadar

On-demand security scanner. Uses Go Coroutines for SYN scanning and Token Bucket to prevent network congestion.
Fingerprints devices based on Banner/TLS data.
