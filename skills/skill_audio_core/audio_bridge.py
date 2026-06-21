import os
import socket
import threading
import json
import time
from butler.core.ipc_tlv import recv_tlv
from butler.core.blackboard import blackboard

def handle_request(action, **kwargs):
    if action == "run":
        # Start the background bridge
        threading.Thread(target=audio_bridge_thread, daemon=True).start()
        return "Audio Core service started in background."
    return f"Action {action} not supported."

def audio_bridge_thread():
    """
    Bridges Go FFT data to:
    1. Global Blackboard (for other skills)
    2. STM32 (Serial)
    3. UI (via ModernBridge/WebSocket - placeholder)
    """
    socket_path = "butler_audio.sock"
    if os.path.exists(socket_path):
        os.remove(socket_path)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(1)

    print(f"Python Audio Bridge listening on {socket_path}...")

    while True:
        conn, _ = server.accept()
        try:
            while True:
                t, v = recv_tlv(conn)
                if t is None: break

                if t == 1: # FFT Data
                    # Update Blackboard for UI/Skills
                    blackboard.write("audio.fft_data", list(v), ttl=0.1)

                    # Extract energy for STM32 [0xAA][B][M][T][0xBB]
                    # Simple extraction: first, middle, and last chunks
                    if len(v) >= 3:
                        energy_frame = bytearray([0xAA, v[2], v[15], v[30], 0xBB])
                        # In real use: serial_port.write(energy_frame)
                        blackboard.write("audio.energy", list(energy_frame), ttl=0.1)

        except Exception as e:
            print(f"Bridge error: {e}")
        finally:
            conn.close()
