# Raspberry Pi Zero Deployment Guide for Butler Assistant

This guide provides step-by-step instructions for deploying the Butler voice assistant on a Raspberry Pi Zero W in a headless configuration.

## 1. Prerequisites

Before you begin, ensure you have:

1.  **Assembled Your Hardware:** Your Raspberry Pi Zero W, I2S microphone, and I2S amplifier should be assembled and connected as described in the `HARDWARE_GUIDE.md`.
2.  **Installed Raspberry Pi OS:** Raspberry Pi OS Lite (32-bit) should be installed on your microSD card, and you should be able to connect to the device via SSH.
3.  **Configured Audio:** The I2S audio hardware should be configured and tested as outlined in the `HARDWARE_GUIDE.md`.

## 2. System Preparation

First, update your system's package lists and install the required system-level dependencies.

```bash
# Update package lists and upgrade existing packages
sudo apt-get update && sudo apt-get upgrade -y

# Install system dependencies
# - PortAudio is required for pyaudio
# - espeak is a dependency for pyttsx3 (text-to-speech)
# - git is needed to clone the repository
# - redis-server is used by the application for caching
sudo apt-get install -y portaudio19-dev espeak git redis-server
```

## 3. Application Installation

### Step 3.1: Clone the Repository

Clone the Butler assistant repository from GitHub.

```bash
git clone https://github.com/PAYDAY3/Butler.git
cd Butler
```

### Step 3.2: Create a Virtual Environment

Using a virtual environment is highly recommended to isolate the project's dependencies.

```bash
# Install the virtual environment package
sudo apt-get install -y python3-venv

# Create and activate the virtual environment
python3 -m venv venv
source venv/bin/activate
```
*You will need to run `source venv/bin/activate` every time you open a new terminal session to work on the project.*

### Step 3.3: Install Python Dependencies

Install the required Python packages. This step may take a significant amount of time on a Raspberry Pi Zero.

```bash
pip install -r requirements.txt
```

### Step 3.4: Install the Butler Application

Install the Butler application in editable mode.

```bash
pip install -e .
```

## 4. Configuration

### Step 4.1: Configure API Keys

Create a `.env` file from the example template.

```bash
cp .env.example .env
```

Now, edit the `.env` file and add your secret API keys.

```bash
nano .env
```
Fill in the following values:
```
DEEPSEEK_API_KEY="your_deepseek_api_key"
AZURE_SPEECH_KEY="your_azure_speech_key"
AZURE_SERVICE_REGION="your_azure_service_region"
PICOVOICE_ACCESS_KEY="your_picovoice_access_key"
```

## 5. Running the Application

You can now run the application in headless mode.

```bash
# Ensure your virtual environment is active
source venv/bin/activate

# Run the application
python -m butler.main --headless
```

The assistant should start, and you will see log messages in your terminal. It will automatically begin listening for the "Jarvis" wake word.

## 6. Running as a Service (Optional but Recommended)

To make the assistant start automatically when your Raspberry Pi boots up, it's best to run it as a `systemd` service.

### Step 6.1: Create a Service File

Create a new service file:

```bash
sudo nano /etc/systemd/system/butler.service
```

Paste the following configuration into the file. **Make sure to replace `/home/pi/Butler` with the actual path to the Butler repository on your device.**

```
[Unit]
Description=Butler Voice Assistant
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/Butler
ExecStart=/home/pi/Butler/venv/bin/python -m butler.main --headless
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Step 6.2: Enable and Start the Service

1.  **Reload `systemd`** to make it aware of the new service:
    ```bash
    sudo systemctl daemon-reload
    ```

2.  **Enable the service** to start on boot:
    ```bash
    sudo systemctl enable butler.service
    ```

3.  **Start the service** immediately:
    ```bash
    sudo systemctl start butler.service
    ```

4.  **Check the status** of the service to see if it's running correctly:
    ```bash
    sudo systemctl status butler.service
    ```

You can also view the logs of the service in real-time with:
```bash
journalctl -u butler.service -f
```

Your Butler voice assistant is now fully deployed and will run automatically every time your Raspberry Pi is powered on.
