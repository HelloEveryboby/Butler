#!/bin/bash
# Start Butler in Modern (Web UI) mode

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )/.."
cd "$DIR"

# Detect and use portable runtime if available
PYTHON_CMD="python3"
if [ -f "./runtime/bin/python3" ]; then
    PYTHON_CMD="./runtime/bin/python3"
    export PYTHONPATH=$PYTHONPATH:.
elif [ -f "./runtime/python" ]; then
    PYTHON_CMD="./runtime/python"
    export PYTHONPATH=$PYTHONPATH:.
fi

$PYTHON_CMD -m butler.butler_app --modern
