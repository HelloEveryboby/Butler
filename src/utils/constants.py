from pathlib import Path
import os

# Project Root: /Butler/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Core Directories
BUTLER_DIR = PROJECT_ROOT / "butler"
PACKAGE_DIR = PROJECT_ROOT / "package"
PLUGIN_DIR = PROJECT_ROOT / "plugin"
SKILLS_DIR = PROJECT_ROOT / "skills"
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
LOGS_DIR = PROJECT_ROOT / "logs"
ASSETS_DIR = PROJECT_ROOT / "assets"
DOCS_DIR = PROJECT_ROOT / "docs"
PROGRAMS_DIR = PROJECT_ROOT / "programs"

# Data Subdirectories
AUDIT_LOGS_DIR = DATA_DIR / "audit_logs"
BUTLER_MEMORY_DIR = DATA_DIR / "butler_memory"
TEAM_DIR = DATA_DIR / "team"
INBOX_DIR = TEAM_DIR / "inbox"
NOTIFICATIONS_DB = DATA_DIR / "notifications.db"
SCHEDULED_TASKS_JSON = DATA_DIR / "scheduled_tasks.json"

# Config Files
SYSTEM_CONFIG_YAML = CONFIG_DIR / "config.yaml"
SYSTEM_CONFIG_JSON = CONFIG_DIR / "system_config.json" # Legacy
SKILLS_LOCK_JSON = PROJECT_ROOT / "skills-lock.json"

# Ensure essential directories exist
for _dir in [DATA_DIR, CONFIG_DIR, LOGS_DIR, AUDIT_LOGS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

def resolve_path(relative_path: str) -> Path:
    """Resolves a relative path against the project root."""
    return PROJECT_ROOT / relative_path
