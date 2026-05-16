#!/bin/bash
# This script starts the Butler application.
# It ensures that the script is run from the project root.

echo "Starting Butler application..."

# Get the directory where the script is located (bin/)
BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Change to the project root (parent of bin/)
cd "$BIN_DIR/.."
PROJECT_ROOT=$(pwd)

# 1. Ensure .env exists (out-of-the-box)
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    echo "Initializing .env from .env.example..."
    cp .env.example .env
  else
    echo "Warning: .env.example not found. Creating empty .env..."
    touch .env
  fi
fi

# 2. Check and install dependencies automatically (Portable mode preferred)
# We check if lib_external exists as a proxy for 'already installed'
if [ ! -d "lib_external" ] && [ ! -d "venv" ]; then
    echo "First time setup: Installing dependencies in portable mode..."
    python3 -m package.dependency_manager install_all
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
$PYTHON_CMD -m butler.butler_app "$@"

echo "Application closed."
