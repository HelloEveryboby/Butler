#!/bin/bash
# Build script for hybrid_net Go module
# Part of BHL (Butler Hybrid-Link) System

set -e

# Change to the directory of the script
cd "$(dirname "$0")"

echo "Building hybrid_net module (Optimized for size)..."

# Check if go is installed
if ! command -v go &> /dev/null
then
    echo "Error: go is not installed. Please install Go to build this module."
    exit 1
fi

# Clean up previous builds
rm -f hybrid_net_exec

# Build the binary with size optimizations
# -s: omit the symbol table and debug information
# -w: omit the DWARF symbol table
go build -ldflags="-s -w" -o hybrid_net_exec net_service.go

# Verify binary existence
if [ -f "hybrid_net_exec" ]; then
    echo "Successfully built hybrid_net_exec"
    chmod +x hybrid_net_exec
    ls -lh hybrid_net_exec
else
    echo "Error: Failed to build hybrid_net_exec"
    exit 1
fi
