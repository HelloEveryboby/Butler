#!/bin/bash
# Build script for BHL Go Router
set -e
cd "$(dirname "$0")"
go build -ldflags="-s -w" -o comm_router_go router_core.go
chmod +x comm_router_go
