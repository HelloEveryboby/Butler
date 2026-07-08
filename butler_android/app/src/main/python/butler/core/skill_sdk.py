import os
import sys
import json
import ctypes
import logging
import gc
import asyncio
import signal
from typing import Any, Dict, Optional

logger = logging.getLogger("SkillSDK")

# Global throttle interval for DRAS (Mobile Active Throttling)
_throttle_interval = 0.0

def trigger_global_throttling(active: bool):
    """Called by Java/Kotlin side via Chaquopy when thermal/battery thresholds are hit."""
    global _throttle_interval
    _throttle_interval = 0.05 if active else 0.0
    logger.info(f"Mobile DRAS: Throttling set to {active} (interval={_throttle_interval})")

def setup_mobile_dras():
    if sys.platform != 'win32':
        try:
            # Patch the default event loop to inject throttling
            _inject_event_loop_throttling()
        except Exception as e:
            logger.debug(f"Failed to setup DRAS: {e}")

def _inject_event_loop_throttling():
    """
    Monkey-patch asyncio.BaseEventLoop._run_once to inject micro-sleeps
    when DRAS throttling is active. This ensures ALL async tasks are slowed down.
    """
    loop = asyncio.get_event_loop()
    if not hasattr(loop, "_original_run_once"):
        loop._original_run_once = loop._run_once

        def throttled_run_once():
            if _throttle_interval > 0:
                time.sleep(_throttle_interval)
            loop._original_run_once()

        loop._run_once = throttled_run_once
        logger.info("Mobile DRAS: Event loop throttling injected.")

class NativeOCR:
    """Bridges to Android ML Kit via Chaquopy Java Bridge."""
    @staticmethod
    def recognize_text(image_path: str) -> str:
        try:
            from java import jclass
            import time
            # ML Kit Text Recognition usage via Chaquopy
            TextRecognition = jclass("com.google.mlkit.vision.text.TextRecognition")
            TextRecognizerOptions = jclass("com.google.mlkit.vision.text.latin.TextRecognizerOptions")
            InputImage = jclass("com.google.mlkit.vision.common.InputImage")
            File = jclass("java.io.File")
            Uri = jclass("android.net.Uri")
            Python = jclass("com.chaquo.python.Python")

            recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
            image = InputImage.fromFilePath(Python.getPlatform().getApplication(),
                                           Uri.fromFile(File(image_path)))

            # ML Kit process returns a Task object
            task = recognizer.process(image)

            # Block until task is complete (runs in Python worker thread, doesn't block UI)
            while not task.isComplete():
                time.sleep(0.01)

            if task.isSuccessful():
                return task.getResult().getText()
            else:
                raise RuntimeError(f"ML Kit Native OCR Process Failure: {task.getException().getMessage()}")
        except ImportError:
            return "ML Kit not available (non-Android)"
        except Exception as e:
            return f"OCR Error: {str(e)}"

class SkillSDK:
    @staticmethod
    def get_input() -> Dict[str, Any]:
        line = sys.stdin.readline()
        return json.loads(line) if line else {}

    @staticmethod
    async def task_wrapper(coro):
        """Wrapper for skill tasks to inject DRAS throttling."""
        if _throttle_interval > 0:
            await asyncio.sleep(_throttle_interval)
        return await coro

    @staticmethod
    def send_result(data: Any):
        print(json.dumps({"action": "result", "payload": data}), flush=True)

    @staticmethod
    def speak(text: str):
        msg = {"action": "speak", "payload": {"text": text}}
        print(json.dumps(msg), flush=True)

    @staticmethod
    def ui_print(text: str, tag: str = "ai_response"):
        msg = {"action": "ui_print", "payload": {"text": text, "tag": tag}}
        print(json.dumps(msg), flush=True)

    @staticmethod
    def set_result(data: Any):
        """Alias for send_result used by some skills."""
        SkillSDK.send_result(data)

    @staticmethod
    def write_blackboard(key: str, value: Any, ttl: float = 60.0):
        """Write to Ephemeral Sandbox Blackboard."""
        msg = {
            "action": "blackboard_write",
            "payload": {"key": key, "value": value, "ttl": ttl}
        }
        print(json.dumps(msg), flush=True)

    @staticmethod
    def cleanup():
        from butler.core.vault_wiper import wipe_all_sensitive
        wipe_all_sensitive()
        gc.collect()

# Initialize mobile DRAS on import
setup_mobile_dras()

# Export sdk instance for legacy/test compatibility
sdk = SkillSDK()
