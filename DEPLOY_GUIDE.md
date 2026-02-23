# Butler (Jarvis) Deployment Guide

This comprehensive guide provides all the necessary steps to set up, configure, and run the Butler (formerly Jarvis) voice assistant application from the source code.

## 1. Project Analysis

- **Purpose**: Butler is a Python-based personal assistant operated by voice or text. It can perform a wide range of tasks through an extensible plugin and program architecture.
- **Core Technologies**:
    - **Backend**: Python 3.8+
    - **Speech Recognition**: Azure Cognitive Services
    - **Natural Language Processing**: DeepSeek API
    - **System Dependencies**: PortAudio, Redis

---

## 2. Prerequisites

Before you begin, ensure your system has the following software installed.

### 2.1. System-level Dependencies

1.  **Python**: Version 3.8 or newer is required. You can download it from [python.org](https://python.org/).

2.  **PortAudio**: This library is essential for audio input and output (`pyaudio`).
    -   **On Debian/Ubuntu**:
        ```bash
        sudo apt-get update && sudo apt-get install -y portaudio19-dev
        ```
    -   **On macOS (using Homebrew)**:
        ```bash
        brew install portaudio
        ```
    -   **On other systems**: Please use your system's package manager to install the PortAudio development package.

3.  **Redis**: The web crawler functionality depends on a running Redis server.
    -   **On Debian/Ubuntu**:
        ```bash
        sudo apt-get install -y redis-server
        sudo systemctl start redis-server
        sudo systemctl enable redis-server
        ```
    -   **On macOS (using Homebrew)**:
        ```bash
        brew install redis
        brew services start redis
        ```
    -   Ensure Redis is running on the default port (`localhost:6379`).

---

## 3. Installation Steps

Follow these steps to install the Butler application and its dependencies.

### 3.1. Clone the Repository

First, clone the project repository to your local machine.
```bash
git clone <repository_url>
cd <repository_name>
```

### 3.2. Install Python Dependencies

Install all required Python libraries using the `requirements.txt` file. It is highly recommended to do this within a virtual environment.
```bash
# (Optional but recommended) Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt
```

### 3.3. Install the Butler Application

Finally, install the Butler application itself in editable mode. This makes the `butler` command available in your shell and ensures any changes you make to the source code are immediately reflected.
```bash
pip install -e .
```

---

## 4. Configuration

The application requires API keys for its core AI services.

1.  **Create `.env` file**: Copy the example template to a new file named `.env`. This file will store your secret keys.
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env` file**: Open the `.env` file in a text editor and fill in your secret keys.
    ```dotenv
    # DeepSeek API Key for Natural Language Processing
    DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY_HERE

    # Azure Cognitive Speech Services for Speech-to-Text
    AZURE_SPEECH_KEY=YOUR_AZURE_SPEECH_KEY_HERE
    AZURE_SERVICE_REGION=YOUR_AZURE_SERVICE_REGION
    ```
    *Replace `YOUR_..._HERE` with your actual API keys. The `AZURE_SERVICE_REGION` should match the region of your Azure Speech resource (e.g., `eastus`, `chinaeast2`).*

---

## 5. Required Data Files

The application requires a startup sound effect.

-   **Action Required**: Place a startup sound file named `jarvis.wav` inside the `butler/resources/` directory. If the `resources` directory does not exist, you must create it first.
    ```bash
    mkdir -p butler/resources
    # Now, move your sound file to this directory
    # mv /path/to/your/jarvis.wav butler/resources/
    ```

---

## 6. Running the Application

Once all the installation and configuration steps are complete, you can run the application with a single command:
```bash
butler
```
The application will start, and you can begin interacting with it through the GUI and voice commands.

---

## 7. Customizing Assistant Behavior with Prompts

Butler's behavior and personality are controlled by system prompts that are sent to the DeepSeek language model. You can customize these prompts by editing the `butler/prompts.json` file.

This file contains different prompts for different tasks:
-   `nlu_intent_extraction`: This prompt instructs the AI on how to analyze user commands to determine intent and extract information. Modifying this can improve command recognition.
-   `general_response`: This prompt defines the assistant's default personality for conversational replies. You can change this to make the assistant more formal, creative, or humorous.

To change a prompt, simply edit the `prompt` value for the desired key in the JSON file. The changes will take effect the next time you start the application.

---

## 8. Building a Standalone Executable (Advanced)

For easier distribution, you can build a standalone executable using `PyInstaller`.

1.  **Ensure `PyInstaller` is installed**:
    ```bash
    pip install pyinstaller
    ```

2.  **Run the build command**:
    Make sure you have already placed the `jarvis.wav` file in the correct directory as described in Section 5.
    ```bash
    pyinstaller --name Butler --onefile --add-data "butler/resources:butler/resources" butler.butler_app.py
    ```

The final executable will be located in the `dist/` directory.
