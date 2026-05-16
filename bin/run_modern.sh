#!/bin/bash
# Get the directory where the script is located (bin/)
BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Change to the project root (parent of bin/)
cd "$BIN_DIR/.."

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
if [ ! -d "lib_external" ] && [ ! -d "venv" ]; then
    echo "First time setup: Installing dependencies in portable mode..."
    python3 -m package.dependency_manager install_all
fi

# Detect and use portable runtime if available
PYTHON_CMD="python3"
if [ -f "./runtime/bin/python3" ]; then
    PYTHON_CMD="./runtime/bin/python3"
    export PYTHONPATH=$PYTHONPATH:.
elif [ -f "./runtime/python" ]; then
    PYTHON_CMD="./runtime/python"
    export PYTHONPATH=$PYTHONPATH:.
fi

$PYTHON_CMD -m frontend.program.modern_app "$@"
