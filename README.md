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

## Project Structure

The project is organized into several key directories:

*   `butler/`: The core of the Butler assistant, including the main application logic, GUI, and conversational AI integration.
*   `local_interpreter/`: A standalone, sandboxed code interpreter for safely executing code generated from natural language.
*   `package/`: A collection of standalone modules and tools that can be invoked by the Butler assistant.
*   `plugin/`: A framework for creating and managing plugins to extend Butler's capabilities.
*   `logs/`: Contains log files for the application.

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

The `package/` directory contains modules that provide various functionalities. These modules fall into two categories:

*   **Runnable Packages**: These are standalone tools designed to be executed directly by Butler. To be recognized as a runnable package, the Python file must contain a `run()` function, which serves as its entry point. You can map a user-friendly command to these packages in `butler/program_mapping.json`.

*   **Utility Modules**: These are libraries of functions (e.g., `math.py`) intended to be imported and used by other parts of the application, such as plugins or other packages. They do not have a `run()` function and are not directly executable by the user through a command.

To add a new runnable package, create a Python file in the `package/` directory, implement a `run()` function, and consider adding an entry for it in `butler/program_mapping.json`.

## Plugins

The `plugin/` directory contains plugins that extend the functionality of the Butler assistant. Each plugin should inherit from `plugin.abstract_plugin.AbstractPlugin` and implement the required methods.

The `PluginManager` will automatically load any valid plugins placed in this directory.

## Contribution

We welcome contributions! Please feel free to submit a Pull Request. When contributing, please ensure your code adheres to the project's style and that you update documentation where appropriate.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
