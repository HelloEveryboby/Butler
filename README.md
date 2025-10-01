# Butler - An Intelligent Assistant System

Butler is a feature-rich, intelligent assistant system developed in Python. It integrates natural language processing, a powerful algorithms library, dynamic program management, a sandboxed code interpreter, and an extensible plugin system. Designed with a modular architecture, Butler is capable of performing a wide range of complex tasks through text, voice, or API commands.

This project also includes a comprehensive library of common algorithms and exposes them through a developer-friendly REST API, making them accessible from any programming language.

## Features

*   **Conversational AI**: Uses the DeepSeek API for natural language understanding and response generation.
*   **Extensible Program Management**: Dynamically loads and executes external program modules.
*   **Advanced Algorithm Library**: A rich, efficient, and well-documented library of algorithms.
*   **Developer-Friendly API**: A dedicated REST API for direct access to the algorithm library.
*   **Interactive Command Panel**: A Tkinter-based GUI for text-based interaction.
*   **Voice Interaction**: Supports voice commands and speech synthesis using Azure Cognitive Services.
*   **Local Code Interpreter**: A secure, sandboxed environment for executing Python code generated from natural language commands.
*   **Plugin System**: Easily extend Butler's functionality with custom plugins.

## Architecture

The Butler assistant is built on a modular and extensible architecture designed for flexibility and scalability. At its core is the `Jarvis` class, which acts as the central orchestrator, managing the flow of information and coordinating the various components of the system.

The key architectural components include:

*   **Command Handling**: User input is processed through a sophisticated command handling system that supports multiple execution paths. Simple commands can be handled directly by the `Jarvis` class, while more complex queries are routed to the appropriate subsystem. The system defaults to a powerful local code interpreter but provides a `/legacy` command to access an older, intent-based system.

*   **Local Code Interpreter**: For advanced commands, Butler uses a sandboxed local interpreter that can execute Python code generated from natural language. This component is encapsulated within the `Interpreter` class, which leverages an `Orchestrator` to generate code and a `code_executor` to run it in a secure environment.

*   **Plugin System**: Butler's functionality can be extended through a dynamic plugin system. The `PluginManager` is responsible for discovering, loading, and executing plugins from the `plugin/` directory. Each plugin is a self-contained module that can be designed to perform specific tasks, such as searching the web, managing a to-do list, or interacting with external APIs.

*   **Package Management**: The `package/` directory contains a collection of standalone tools and utilities that can be invoked by the assistant. These packages are dynamically discovered and can be executed as independent programs, providing a simple way to add new capabilities to the system.

*   **User Interface**: The primary user interface is a Tkinter-based GUI, managed by the `CommandPanel` class. This component provides a text-based interface for interacting with the assistant and can be extended to support other forms of interaction, such as voice commands.

This modular design allows for independent development and testing of each component, making the system easy to maintain and expand.

## Command Processing Workflow

User commands are processed through a flexible and multi-layered workflow that ensures the appropriate component handles the request. The default processing path is the local code interpreter, but users can access the legacy intent-based system by prefixing their command with `/legacy`.

The workflow is as follows:

1.  **Input**: The user enters a command through the Tkinter GUI, voice input, or another interface.

2.  **Routing**:
    *   If the command starts with `/legacy`, it is routed to the legacy intent-based system. The system uses the DeepSeek API to perform Natural Language Understanding (NLU) and identify the user's intent and any associated entities. The command is then passed to the appropriate handler based on the identified intent.
    *   Otherwise, the command is sent to the **Local Code Interpreter** by default.

3.  **Execution**:
    *   **Local Interpreter**: The `Interpreter` class sends the natural language command to the `Orchestrator`, which uses an LLM to generate Python code. This code is then executed in a secure, sandboxed environment by the `code_executor`.
    *   **Legacy System**: If an intent is matched, the corresponding handler in the `Jarvis` class is invoked. This may involve calling a function from the `algorithms` library, interacting with a plugin, or executing a package.
    *   **Plugin Execution**: If the command is intended for a plugin, the `PluginManager` will identify the correct plugin and execute its `run` method.
    *   **Package Execution**: If the command corresponds to a package, the `Jarvis` class will execute the package's `run()` function.

4.  **Output**: The result of the command execution is displayed to the user through the GUI and, if applicable, spoken back to the user using text-to-speech.

This layered approach allows Butler to handle a wide range of commands, from simple, predefined actions to complex, dynamically generated code, while maintaining a clear and organized structure.

## Project Structure

The project is organized into several key directories, each with a specific role:

*   `butler/`: The core of the Butler assistant. This directory contains the main application logic, including the `Jarvis` class which orchestrates the entire system. It also houses the Tkinter-based GUI (`CommandPanel.py`), conversational AI integration, and the REST API for the algorithms library.

*   `local_interpreter/`: A standalone, sandboxed code interpreter. This component is responsible for safely executing Python code generated from natural language commands. It features an `Orchestrator` that translates natural language to code and an `Executor` that runs the code in a secure environment, preventing it from affecting the host system.

*   `package/`: A collection of standalone modules and tools that can be invoked by the Butler assistant. Each `.py` file in this directory is treated as a separate package and must contain a `run()` function to be executable. This allows for easy extension of Butler's capabilities with new, independent tools.

*   `plugin/`: A framework for creating and managing plugins to extend Butler's core functionality. Plugins are more deeply integrated than packages and are managed by the `PluginManager`. They must inherit from `AbstractPlugin` and can be used to add complex features like web search, long-term memory, or interaction with external services.

*   `logs/`: Contains log files for the application, which are useful for debugging and monitoring the system's behavior.

## Getting Started

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/PAYDAY3/Butler.git
    cd Butler
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure API Keys:**
    Create a `.env` file in the root directory by copying the `.env.example` file. Then, add your API keys:
    ```
    DEEPSEEK_API_KEY="your_deepseek_api_key"
    AZURE_SPEECH_KEY="your_azure_speech_key"
    AZURE_SERVICE_REGION="your_azure_service_region"
    ```

## Usage

### Easy Launch (Recommended)

Once you have installed the dependencies and configured your API keys, you can start the application easily:

*   **On Windows:** Simply double-click the `run.bat` file.
*   **On macOS or Linux:** Run the `run.sh` script from your terminal with `./run.sh`, or double-click it in your file manager (you may need to grant it execute permissions first with `chmod +x run.sh`).

These scripts will open the main application with its graphical user interface.

### Manual Launch

If you prefer, you can still run the application manually from the command line.

#### Butler Assistant

To start the Butler assistant with its GUI:

```bash
python -m butler.main
```

You can interact with the assistant by typing commands in the input box or by using voice commands.

### Local Interpreter

To run the standalone local code interpreter:

```bash
python -m local_interpreter.main
```

This will start a command-line interface where you can type natural language commands to be executed in a sandboxed environment.

### Algorithms API

To start the REST API server for the algorithms library:

```bash
python -m butler.api
```

The server will run on `http://localhost:5001`. You can then make requests to the available endpoints (e.g., `/api/sort`, `/api/search`).

## Packages

The `package/` directory contains a collection of tools and utilities that can be executed by the Butler assistant. Each module in this directory should have a `run()` function, which serves as the entry point for execution.

To add a new package, simply create a new Python file in the `package/` directory and implement a `run()` function within it. Butler will automatically discover and be able to execute it.

## Plugins

The `plugin/` directory contains plugins that extend the functionality of the Butler assistant. Each plugin should inherit from `plugin.abstract_plugin.AbstractPlugin` and implement the required methods.

The `PluginManager` will automatically load any valid plugins placed in this directory.

## Contribution

We welcome contributions! Please feel free to submit a Pull Request. When contributing, please ensure your code adheres to the project's style and that you update documentation where appropriate.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
