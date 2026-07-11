---
name: WebSecurityTester
description: Comprehensive web security testing orchestrator (Recon, Scanner, Logic Checklist).
triggers:
  - "test web security"
  - "audit web app"
  - "scan website"
provides:
  - "sec.web_report"
python_entry: main.py
risk: high
---

# WebSecurityTester

Butler's orchestrator for web security testing. It coordinates external tools like Nmap, Sqlmap, and Nuclei to provide deep security insights.

## Capabilities
- **Recon**: Port scanning and directory discovery.
- **Scanning**: Automated vulnerability detection for SQLi, XSS, etc.
- **Checklist**: AI-powered business logic vulnerability checklists.

## Usage
- "Help me test the security of http://example.com"
- "Generate a security checklist for a payment flow"
- "Scan http://example.com/login.php for SQL injection"
