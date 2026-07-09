---
name: CloudSecurityAuditor
description: Infrastructure and Container security auditing using Trivy and Cloud CLIs.
triggers:
  - "audit cloud"
  - "scan container"
  - "k8s security check"
provides:
  - "sec.cloud_report"
python_entry: main.py
risk: high
---

# CloudSecurityAuditor

Audits cloud configurations and container images for vulnerabilities and misconfigurations.

## Tools Integrated
- **Trivy**: Vulnerability scanning for images, filesystems, and git repositories.
- **AWS/Aliyun CLI**: Config auditing (IAM, S3/OSS permissions).
