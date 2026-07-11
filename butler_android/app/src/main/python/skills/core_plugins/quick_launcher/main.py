import os
import subprocess
import logging
from typing import Dict, Any

logger = logging.getLogger("quick_launcher")
_context = None

DEFAULT_MAPPINGS = {
    "system": "python3 -c \"from skills.core_plugins.system_monitor.main import handle_request; print(handle_request('run'))\"",
    "memos": "python3 butler_cli.py list-memos",
    "ping": "ping -c 3 google.com" if os.name != "nt" else "ping -n 3 google.com"
}


def initialize_core(context) -> None:
    """
    Hook called by SkillManager upon load.
    Registers listeners on the EventBus for rapid integration.
    """
    global _context
    _context = context
    logger.info("quick_launcher core plugin successfully initialized with privileges.")

    # Populate default mappings in data storage if not already present
    try:
        existing = _context.data_storage.load("quick_launcher", "mappings")
        if existing is None:
            _context.data_storage.save("quick_launcher", "mappings", DEFAULT_MAPPINGS)
            logger.info("Default quick_launcher mappings populated.")
    except Exception as e:
        logger.error(f"Failed to populate default launcher mappings: {e}")

    # Listen to fast-launch triggers via EventBus
    _context.event_bus.subscribe("quick_launcher:trigger", trigger_via_event)


def trigger_via_event(cmd_alias: str) -> None:
    """Callback for EventBus triggers."""
    logger.info(f"Received quick launch event for alias: {cmd_alias}")
    res = handle_request("launch", alias=cmd_alias)
    if _context:
        _context.event_bus.emit("ui_output", f"🚀 [快速启动] 执行 '{cmd_alias}' 结果:\n{res}", "ai_response", None)


def handle_request(action: str, **kwargs) -> Any:
    """
    Handles request for quick launcher actions:
    - 'list': List registered shortcuts.
    - 'register': Map a shortcut. Usage: handle_request('register', alias='mycmd', command='echo hello')
    - 'launch': Execute a shortcut. Usage: handle_request('launch', alias='mycmd')
    - 'delete': Remove a shortcut mapping. Usage: handle_request('delete', alias='mycmd')
    """
    global _context
    if _context is None:
        return "Error: Core plugin context is not initialized."

    # Load mappings
    try:
        mappings = _context.data_storage.load("quick_launcher", "mappings") or {}
    except Exception:
        mappings = DEFAULT_MAPPINGS.copy()

    if action == "list":
        if not mappings:
            return "No registered shortcuts."
        report = ["🚀 **当前注册的快捷启动指令**:"]
        for alias, cmd in mappings.items():
            report.append(f"- **{alias}** → `{cmd}`")
        return "\n".join(report)

    elif action == "register":
        alias = kwargs.get("alias")
        command = kwargs.get("command")
        if not alias or not command:
            return "Error: Both 'alias' and 'command' parameters are required for registration."

        mappings[alias] = command
        _context.data_storage.save("quick_launcher", "mappings", mappings)
        return f"Successfully registered shortcut: **{alias}** → `{command}`"

    elif action == "delete":
        alias = kwargs.get("alias")
        if not alias:
            return "Error: 'alias' parameter is required for deletion."
        if alias in mappings:
            del mappings[alias]
            _context.data_storage.save("quick_launcher", "mappings", mappings)
            return f"Successfully deleted shortcut alias: **{alias}**"
        else:
            return f"Error: Shortcut alias '{alias}' not found."

    elif action == "launch":
        alias = kwargs.get("alias")
        if not alias:
            return "Error: 'alias' parameter is required for launching."

        command = mappings.get(alias)
        if not command:
            return f"Error: Shortcut alias '{alias}' not registered."

        # Execute safe system execution
        try:
            logger.info(f"Executing quick command for {alias}: {command}")
            # Run in a non-blocking subprocess with timeout
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15
            )
            output = result.stdout or result.stderr or "Success (No output)"
            return output.strip()
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after 15s."
        except Exception as e:
            return f"Error during execution: {str(e)}"

    return f"Error: Unsupported action '{action}'."
