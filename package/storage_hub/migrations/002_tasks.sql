-- Butler Database Migration - 002_tasks
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    agent TEXT,
    status TEXT NOT NULL, -- e.g., pending, running, completed, failed
    input TEXT,
    output TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
