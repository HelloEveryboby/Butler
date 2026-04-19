#!/bin/bash
# This script starts the Butler application.
# It ensures that the script is run from the project root.

echo "Starting Butler application..."

# Get the directory where the script is located (bin/)
BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Change to the project root (parent of bin/)
cd "$BIN_DIR/.."
PROJECT_ROOT=$(pwd)

# Check if .env file exists. If not, run the installation script.
if [ ! -f ".env" ]; then
  echo "Configuration file (.env) not found."
  echo "Running setup script..."
  # Run the installation script
  ./bin/install.sh
fi

# Detect and use portable runtime if available
PYTHON_CMD="python3"
if [ -f "./runtime/bin/python3" ]; then
    PYTHON_CMD="./runtime/bin/python3"
    echo "Using portable Python runtime (Linux)."
    export PYTHONPATH=$PYTHONPATH:.
elif [ -f "./runtime/python" ]; then
    PYTHON_CMD="./runtime/python"
    echo "Using portable Python runtime (Darwin/Generic)."
    export PYTHONPATH=$PYTHONPATH:.
fi

# Run the main application using the python module flag
echo "Launching main application..."
$PYTHON_CMD -m butler.butler_app

echo "Application closed."
