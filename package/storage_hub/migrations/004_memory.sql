-- Butler Database Migration - 004_memory
CREATE TABLE IF NOT EXISTS memory (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL, -- short_term, long_term, preference
    content TEXT NOT NULL,
    metadata TEXT, -- JSON metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
