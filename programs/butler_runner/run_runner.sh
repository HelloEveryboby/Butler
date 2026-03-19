#!/bin/bash
# Butler-Runner Pro Portable Launcher (Linux/macOS)

SERVER_IP="127.0.0.1"
TOKEN="BUTLER_SECRET_2026"
RUNNER_ID=$(hostname)

echo "---------------------------------------------------"
echo " Butler-Runner Pro Portable Launcher"
echo " Host: $SERVER_IP"
echo " Runner ID: $RUNNER_ID"
echo "---------------------------------------------------"

if [ ! -f "./runner" ]; then
    echo "[ERROR] runner binary not found! Please compile it first."
    exit 1
fi

chmod +x ./runner
echo "[INFO] Starting runner in background..."
nohup ./runner -server "ws://$SERVER_IP:8000/ws/butler" -token "$TOKEN" -id "$RUNNER_ID" > runner.log 2>&1 &

echo "[SUCCESS] Runner is now running in the background. Check runner.log for details."
echo "PID: $!"
sleep 2
