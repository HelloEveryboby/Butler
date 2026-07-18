-- Butler Database Migration - 001_users
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    settings TEXT, -- JSON configuration/settings
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
