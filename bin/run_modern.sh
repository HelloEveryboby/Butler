#!/bin/bash
# Get the directory where the script is located (bin/)
BIN_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# Change to the project root (parent of bin/)
cd "$BIN_DIR/.."

python3 -m frontend.program.modern_app
