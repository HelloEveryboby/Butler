#!/bin/bash
# Build script for BHL C SHM Bus
set -e
cd "$(dirname "$0")"
gcc -O2 -Iinclude shm_service.c -o comm_bus_c
chmod +x comm_bus_c
