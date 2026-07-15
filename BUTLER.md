# Butler (Jarvis) Security & Execution Policy (BUTLER.md)

This document contains the core behavioral guidelines, safety rules, and operational constraints for the Butler (Jarvis) System Agent and Go executing runners. Both LLM decision-making loops and local system interceptors must align with these guidelines to prevent dangerous actions and ensure system stability.

## 🛡️ Core Security Constraints

1. **Destructive Commands Restricted**
   - Commands that delete files recursively or format storage blocks are strictly restricted.
   - Specifically, wildcards (`*`) or recursive flags inside sensitive root-level paths or major system folders are forbidden.
   - For example, commands containing `rm -rf /` or similar system-destroying formats must be blocked instantly by local interceptors.

2. **Privilege Elevation & Approval Protocol**
   - Any execution requiring administrative permissions (such as utilizing `sudo`, `runas`, or attempting to write to system-level directories like `/etc`, `/System`, or `C:\Windows`) MUST be intercepted.
   - The execution must be suspended immediately, triggering the standard **AskForApproval** protocol. This prompts the user for explicit confirmation (by typing `/approve` or clicking "Authorize" on GUI dashboards).

3. **Safe Environment Directory Scope**
   - Local command runs should be restricted to user-safe work zones, project workspaces, or temp directories unless explicitly permitted.
   - Direct execution or modification of system registry keys, core service configurations, or security credentials should always go through verification.

4. **Network Access Whitelisting**
   - Avoid executing arbitrary scripts retrieved dynamically from untrusted remote URLs via raw `curl | sh` or similar pipelines.
   - Always verify and isolate network-bound task steps inside the sandbox.

## 🛠️ Performance & System Health Guidelines

1. **Resource Awareness**
   - Long-running shell commands or process executions should be throttled or run in the background.
   - Active CPU/Memory status must be evaluated before dispatching compute-intensive format conversions or media processing.

2. **Implicit Skill Reuse**
   - Instead of writing custom Python or shell scripts to execute common automated tasks (like file zipping/unzipping, file-format conversions, or system diagnostics), always favor calling **existing local Skills** (such as `format_convert`, `archive_manager`). This ensures higher speed, less prompt overhead, and predictable, secure execution paths.

3. **Graceful Error Handling & Self-Healing**
   - If a command fails, report the partial execution results instead of silently exiting.
   - Attempt automatic diagnostic analysis using local self-healing scripts.
