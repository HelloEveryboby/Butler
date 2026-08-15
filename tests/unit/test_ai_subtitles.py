import os
import sys
import json
import time
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from skills.ai_subtitles.main import SubtitleEngine, handle_request

def test_subtitle_engine_stream():
    engine = SubtitleEngine()
    events = []

    def on_event(data):
        events.append(data)

    engine.start_stream(on_event)
    time.sleep(1.2)
    engine.stop_stream()

    assert len(events) > 0
    assert "original" in events[0]
    assert "translated" in events[0]

def test_ai_subtitles_handle_request():
    res = handle_request("push_subtitle", original="Test Hello", translated="测试你好", is_final=True)
    assert res.get("status") == "success"
