-- Butler Database Migration - 003_packages
CREATE TABLE IF NOT EXISTS packages (
    name TEXT PRIMARY KEY,
    version TEXT,
    status TEXT -- e.g., active, disabled, uninstalled
);
