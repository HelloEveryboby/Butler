---
name: LLMSecurityTester
description: Security testing for Large Language Models (Prompt Injection, Jailbreaking).
triggers:
  - "test llm"
  - "prompt injection test"
  - "jailbreak check"
provides:
  - "sec.llm_report"
python_entry: main.py
risk: low
---

# LLMSecurityTester

A specialized skill for evaluating the robustness of AI models against adversarial inputs.

## Test Categories
- **Prompt Injection**: Attempting to override system instructions.
- **Jailbreaking**: Testing for bypasses of safety guardrails.
- **Data Leakage**: Checking if the model reveals training data or system prompts.
