import os, sys, json
from butler.butler_app import Jarvis
_jarvis = None
def initialize():
    global _jarvis
    if not _jarvis:
        _jarvis = Jarvis(root=None, usb_screen=None, headless=True)
        _jarvis.main()
def process_message(message):
    if _jarvis: _jarvis.handle_user_command(message)
    return "OK"
def call_plugin(skill_id, action, params):
    if _jarvis: return json.dumps(_jarvis.skill_manager.execute(skill_id, action, **params))
    return "{}"
def cleanup():
    global _jarvis
    if _jarvis: _jarvis.running = False
