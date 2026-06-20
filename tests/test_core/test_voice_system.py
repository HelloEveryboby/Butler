import sys
import os
from pathlib import Path

# Setup path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from butler.core.voice_service import VoiceService
from package.core_utils.config_loader import config_loader

def test_voice_system():
    print("Testing Voice System Refactor...")

    def dummy_callback(text):
        print(f"Callback received text: {text}")

    def dummy_print(msg, tag=None):
        print(f"[{tag}] {msg}")

    # 1. Test Engine Switching
    vs = VoiceService(dummy_callback, dummy_print)
    print(f"Initial mode: {vs.mode}")

    vs.set_voice_mode("local")
    print(f"Switched to mode: {vs.mode}")
    assert vs.mode == "local"

    vs.set_voice_mode("online")
    print(f"Switched back to: {vs.mode}")
    assert vs.mode == "online"

    # 2. Test Local STT if possible (mocked if no audio hardware)
    # We can test if LocalVoiceEngine can transcribe a dummy wav if we had one
    # But for now, we just check if it initializes.
    print("Checking Local Engine initialization...")
    from butler.core.voice_service import LocalVoiceEngine
    local = LocalVoiceEngine()
    print("Local engine initialized.")

    print("Voice System tests passed (Basic logic).")

if __name__ == "__main__":
    try:
        test_voice_system()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
