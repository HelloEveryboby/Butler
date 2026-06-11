import os, sys, json
from butler.butler_app import Butler
_butler = None
def initialize():
    global _butler
    if not _butler:
        _butler = Butler(root=None, usb_screen=None, headless=True)
        _butler.main()
def process_message(message):
    if _butler: _butler.handle_user_command(message)
    return "OK"
def call_plugin(skill_id, action, params):
    if _butler: return json.dumps(_butler.skill_manager.execute(skill_id, action, **params))
    return "{}"
def cleanup():
    global _butler
    if _butler: _butler.running = False
