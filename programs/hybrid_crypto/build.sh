#!/bin/bash
# Build script for hybrid_crypto Rust module

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "Building hybrid_crypto in release mode..."
cargo build --release

echo "Build complete. Binary located at target/release/hybrid_crypto_exec"
