#!/bin/bash
# BUCE Universal Edge Node Build Script

echo "--- Building BUCE Edge Compute Node ---"

if ! command -v arm-none-eabi-gcc &> /dev/null
then
    echo "Error: arm-none-eabi-gcc not found. Please install the ARM toolchain or update CC in Makefile for your specific architecture."
    exit 1
fi

make clean
make all

if [ $? -eq 0 ]; then
    echo "--- Build Successful: buce_edge_node.bin ---"
else
    echo "--- Build Failed ---"
    exit 1
fi
