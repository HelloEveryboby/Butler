---
name: APISecurityTester
description: Specialized testing for RESTful, GraphQL APIs, and JWT/OAuth mechanisms.
triggers:
  - "test api security"
  - "audit graphql"
  - "check jwt"
provides:
  - "sec.api_report"
python_entry: main.py
risk: high
---

# APISecurityTester

Butler's API security specialist. It focuses on modern interface vulnerabilities like GraphQL depth limits, JWT claim tampering, and OAuth flow defects.

## Capabilities
- **JWT Analysis**: Decodes and tests for common JWT vulnerabilities (alg: none, weak secrets).
- **GraphQL Testing**: Introspection checks and complexity analysis.
- **REST Audit**: Automated scanning of REST endpoints.
