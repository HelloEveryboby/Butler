# Butler Hybrid-Link (BHL) Protocol Specification

## 1. Overview
The Butler Hybrid-Link (BHL) protocol is designed for lightweight, cross-language communication between Butler's Python core and specialized modules written in other languages (C++, Go, etc.). It is optimized for both PC environments and future porting to Microcontrollers (MCU).

## 2. Transport Layer
- **PC**: Standard Input (Stdin) and Standard Output (Stdout) pipes.
- **MCU**: UART Serial or MQTT topics.
- **Framing**: Each JSON message must be on a single line (Line-delimited JSON).

## 3. Message Format
BHL follows a simplified JSON-RPC 2.0 structure.

### 3.1 Request (Python -> Module)
```json
{
  "jsonrpc": "2.0",
  "method": "function_name",
  "params": {
    "key": "value"
  },
  "id": "unique_id"
}
```

### 3.2 Response (Module -> Python)
```json
{
  "jsonrpc": "2.0",
  "result": {
    "data": "..."
  },
  "id": "unique_id"
}
```

### 3.3 Error
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32000,
    "message": "Error description"
  },
  "id": "unique_id"
}
```

## 4. Lifecycle
1. **Discovery**: Butler scans `manifest.json` to identify BHL-compatible programs.
2. **Startup**: Butler launches the program.
3. **Execution**: Butler sends a request; the program processes it and returns a response.
4. **Shutdown**: Butler sends an `exit` method or terminates the process.

## 5. Design Principles (揚長避短)
- **Python**: Orchestration, AI integration, string manipulation.
- **C++**: High-performance math, cryptography, hardware-level control.
- **Go**: Concurrent networking, high-throughput data processing.
