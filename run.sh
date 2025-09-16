#!/bin/bash
# This script starts the Butler application.
# It ensures that the script is run from its own directory
# to handle relative paths correctly.

echo "Starting Butler application..."

# Get the directory where the script is located and change to it
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"

# Check if .env file exists. If not, run the installation script.
if [ ! -f ".env" ]; then
  echo "Configuration file (.env) not found."
  echo "Running setup script..."
  # Ensure install.sh is executable
  chmod +x install.sh
  # Run the installation script
  ./install.sh
fi

# Run the main application using the python module flag
echo "Launching main application..."
python -m butler.main

echo "Application closed."
