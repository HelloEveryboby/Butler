---
name: SDLCOrchestrator
description: Automates security checkpoints within CI/CD pipelines (Safe-to-Ship).
triggers:
  - "run security pipeline"
  - "check ci security"
python_entry: main.py
risk: low
---

# SDLCOrchestrator

Integrates various security skills into a unified pipeline report.
Ensures "Security Left Shift" by running SAST/DAST/SCA tools automatically.
