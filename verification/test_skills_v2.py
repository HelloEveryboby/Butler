import logging
import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Mock basic logging and dependencies
logging.basicConfig(level=logging.INFO)

from butler.core.skill_manager import SkillManager

def test_skill_loading():
    print("--- Testing Skill Manager Loading ---")
    sm = SkillManager()
    sm.load_skills()

    print(f"Manifests found: {list(sm.manifests.keys())}")

    if 'translator' in sm.manifests:
        print("✅ Success: 'translator' skill discovered via SKILL.md")
        meta = sm.manifests['translator']
        print(f"Metadata: {meta}")

        instruction = sm.get_skill_instruction('translator')
        print(f"Instruction snippet: {instruction[:50]}...")
    else:
        print("❌ Failure: 'translator' skill not found")

def test_skill_execution():
    print("\n--- Testing Skill Execution (Allowed Script) ---")
    sm = SkillManager()
    sm.load_skills()

    result = sm.execute('translator', 'scripts/translate.py', text="Hello world")
    print(f"Execution Result: {result}")

    if "Translation Result" in str(result):
        print("✅ Success: Script executed and returned expected output")
    else:
        print("❌ Failure: Script execution failed or returned unexpected output")

if __name__ == "__main__":
    test_skill_loading()
    test_skill_execution()
