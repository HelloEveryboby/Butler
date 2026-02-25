#!/bin/bash
# BUCE STM32 Build Script

echo "--- Building BUCE STM32 Firmware ---"

if ! command -v arm-none-eabi-gcc &> /dev/null
then
    echo "Error: arm-none-eabi-gcc not found. Please install the ARM toolchain."
    exit 1
fi

make clean
make all

if [ $? -eq 0 ]; then
    echo "--- Build Successful: buce_stm32.bin ---"
else
    echo "--- Build Failed ---"
    exit 1
fi
