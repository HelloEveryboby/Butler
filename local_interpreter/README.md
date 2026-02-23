# Local Interpreter

A simple, local code interpreter powered by a language model, designed to run safely on resource-constrained devices like the Raspberry Pi Zero. This tool provides a chat-like interface to execute code, perform system tasks, and interact with hardware in a secure, sandboxed environment.

## Features

- **Natural Language Interface**: Control your computer by talking to it in plain English.
- **Pure Python Sandbox**: Untrusted code is executed in a highly-restricted environment. This sandbox is implemented in pure Python, requiring no external dependencies like Docker. It prevents access to the filesystem, network, and other dangerous system calls.
- **Extensible Toolset**: The sandbox can be safely extended with "tools" that allow controlled interaction with the outside world. The current version includes tools for:
    - Listing files in a safe directory.
    - Getting basic system statistics (CPU/Memory).
    - Interacting with Raspberry Pi GPIO pins (placeholder).
- **Lightweight & Portable**: Designed with minimal dependencies to run on devices like the Raspberry Pi Zero.

## How to Run

1.  Navigate to the project directory.
2.  Run the main entry point:
    ```bash
    python3 local_interpreter.interpreter_app.py
    ```
3.  The application will start, and you can type commands at the `>>>` prompt.
4.  Type `exit` to quit the application.

## How It Works

The application consists of three main components:
1.  **Coordinator (`coordinator/`)**: The "brain" that receives user input and (in a real implementation) would query a Large Language Model to generate code. In this version, it simulates code generation based on keywords.
2.  **Executor (`executor/`)**: The "hands" that execute the code. It contains the pure Python sandbox which ensures that only whitelisted functions and modules can be used.
3.  **Tools (`tools/`)**: A collection of safe functions that are injected into the sandbox to give it controlled access to system resources.

### Example Usage

```
Welcome to Local Interpreter MVP. Type 'exit' to quit.
>>> list files in current directory
Orchestrator received: 'list files in current directory'
Simulated generated code:
---
print(list_safe_directory('.'))
---
...
--- Execution Result ---
['notes.txt', 'projects']
------------------------

>>> get system stats
Orchestrator received: 'get system stats'
Simulated generated code:
---
print(get_system_stats())
---
...
--- Execution Result ---
{'cpu_usage_percent': 15.2, 'memory_usage_percent': 25.8}
------------------------
```
