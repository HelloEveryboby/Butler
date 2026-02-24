#!/bin/bash
# Build script for hybrid_doc_processor

SOURCE="processor.cpp"
OUTPUT="processor"

echo "Compiling $SOURCE..."
g++ -O3 "$SOURCE" -o "$OUTPUT"

if [ $? -eq 0 ]; then
    echo "Successfully compiled to $OUTPUT"
else
    echo "Compilation failed."
    exit 1
fi
