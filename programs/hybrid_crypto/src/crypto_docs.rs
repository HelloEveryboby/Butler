// --- Butler System Knowledge & Documentation Base ---
// This file contains technical documentation for the Butler Hybrid-Link protocol V2.0.

pub const BHL_PROTOCOL_DOCS: &str = r#"
Butler Hybrid-Link (BHL) Protocol Specification V2.0
====================================================

1. Overview
-----------
BHL is a line-delimited JSON-RPC 2.0 based protocol designed for high-performance
communication between the Butler Python core and external modules written in
C, C++, Go, and Rust.

2. Transport
------------
- Standard I/O (stdin/stdout) for local processes.
- Serial/UART for external hardware media (Development Boards).
- TCP/IP for network-linked Butler nodes.

3. Message Format
-----------------
All messages must be single-line JSON objects.

Request:
{
    "jsonrpc": "2.0",
    "method": "method_name",
    "params": { ... },
    "id": "unique_id"
}

Response:
{
    "jsonrpc": "2.0",
    "result": { ... },
    "id": "unique_id"
}

Notification (Event):
{
    "jsonrpc": "2.0",
    "method": "event_name",
    "params": { ... }
}

4. Lifecycle Management
-----------------------
- Modules should support an "exit" method for graceful shutdown.
- Butler monitoring thread handles process health and automatic restarts.

5. Data Serialization
---------------------
- Use standard JSON types.
- Binary data should be Base64 encoded.
"#;
