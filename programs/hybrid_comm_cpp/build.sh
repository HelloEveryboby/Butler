#!/bin/bash
# Build script for BHL C++ Processor
set -e
cd "$(dirname "$0")"
g++ -O3 stream_processor.cpp -o comm_processor_cpp
chmod +x comm_processor_cpp
