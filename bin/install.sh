#!/bin/bash

# A script to automate the installation and configuration of the Butler assistant.

echo "Starting Butler installation..."

# Get the project root directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/.."
cd "$DIR"

echo "This script will guide you through the setup process."
echo "-----------------------------------------------------"

# --- Check for dependencies ---
echo "Step 1: Checking for required tools (python3, pip3)..."

command -v python3 >/dev/null 2>&1 || { echo >&2 "Error: python3 is not installed. Please install it and try again."; }
echo "✅ Python 3 found."

command -v pip3 >/dev/null 2>&1 || { echo >&2 "Error: pip3 is not installed. Please install it and try again."; }
echo "✅ pip3 found."

echo "-----------------------------------------------------"

# --- Install Python packages ---
echo "Step 2: Installing Python dependencies..."

echo "Choose Installation Mode:"
echo "1) Standard (System Python/venv)"
echo "2) Portable (External Libs only)"
echo "3) Full Portable (Portable Python Runtime + External Libs)"
read -r install_mode

if [ "$install_mode" == "3" ]; then
    echo "Setting up portable Python runtime..."
    python3 -m package.dependency_manager setup_runtime

    echo "Installing dependencies to lib_external (using system pip)..."
    python3 -m package.dependency_manager install_all
    if [ $? -eq 0 ]; then
        echo "✅ Full Portable setup complete."
    else
        echo >&2 "Error: Failed to install dependencies."
    fi
elif [ "$install_mode" == "2" ]; then
    echo "Installing dependencies to lib_external..."
    python3 -m package.dependency_manager install_all
    if [ $? -eq 0 ]; then
        echo "✅ Local dependencies installed successfully."
    else
        echo >&2 "Error: Failed to install local dependencies."
    fi
else
    echo "Installing dependencies globally/in venv from Setup.py..."
    pip3 install -e .
    if [ $? -eq 0 ]; then
        echo "✅ Python dependencies installed successfully."
    else
        echo >&2 "Error: Failed to install Python dependencies. Please check the output above for errors."
    fi
fi

echo "-----------------------------------------------------"

# --- Configure API Keys ---
echo "Step 3: Configuring API keys..."

# Check if .env file exists
if [ -f ".env" ]; then
    echo "An .env file already exists. Do you want to overwrite it? (y/n)"
    read -r overwrite
    if [ "$overwrite" != "y" ]; then
        echo "Skipping API key configuration."
        echo "-----------------------------------------------------"
        echo "🎉 Butler installation is complete!"
        echo "You can start the assistant by running ./run.sh"
    fi
fi

if [ "$overwrite" == "y" ] || [ ! -f ".env" ]; then
    # Prompt for API keys
    echo "Please enter your DeepSeek API Key:"
    read -s DEEPSEEK_API_KEY

    echo "Please enter your Baidu App ID:"
    read BAIDU_APP_ID

    echo "Please enter your Baidu API Key:"
    read BAIDU_API_KEY

    echo "Please enter your Baidu Secret Key:"
    read -s BAIDU_SECRET_KEY

    # Create .env file
    echo "Creating .env file..."
    cat > .env << EOL
DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY}"
BAIDU_APP_ID="${BAIDU_APP_ID}"
BAIDU_API_KEY="${BAIDU_API_KEY}"
BAIDU_SECRET_KEY="${BAIDU_SECRET_KEY}"
EOL
    echo "✅ .env file created successfully."
fi

echo "-----------------------------------------------------"

echo "🎉 Butler installation and configuration is complete!"
echo "You can now start the assistant by running ./run.sh (on Linux/macOS) or bin/run.bat (on Windows)."
echo "If you are on Linux or macOS, you may need to make the script executable first with: chmod +x run.sh"
