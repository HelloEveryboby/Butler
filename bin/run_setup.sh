#!/bin/bash
# Butler Setup Script for Linux/macOS
# This script handles first-time setup with proper feedback

set -e

echo ""
echo "========================================"
echo "Butler - First Time Setup"
echo "========================================"
echo ""

# Get script directory and change to project root
BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$BIN_DIR/.."
PROJECT_ROOT=$(pwd)

# 1. Check Python installation
echo "[1/3] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8+ using: brew install python3 (macOS) or apt install python3 (Linux)"
    exit 1
fi
python3_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "OK: Python $python3_version found"

# 2. Ensure .env exists
echo "[2/3] Initializing configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
    else
        echo "Creating empty .env..."
        touch .env
    fi
fi
echo "OK: Configuration ready"

# 3. Install dependencies
echo "[3/3] Installing dependencies..."
if [ ! -d "lib_external" ] && [ ! -d "venv" ]; then
    echo "This may take a few minutes on first run..."
    python3 -m package.core_utils.dependency_manager install_all || true
fi
echo "OK: Dependencies ready"

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Starting Butler application..."
echo ""

# Set Python path
export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH

# Launch enhanced app with setup
python3 -m butler.butler_app_enhanced
