import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from butler.core.skill_manager import SkillManager

def test_pdf_skill():
    sm = SkillManager()
    sm.load_skills()

    # Test metadata action
    result = sm.execute("pdf", "metadata", file_path="docs/technical_documentation.md") # Should fail gracefully or find a pdf
    print(f"PDF Metadata Result: {result}")

    # Test create action
    result = sm.execute("pdf", "create", text="Test PDF Content", output="test_output.pdf")
    print(f"PDF Create Result: {result}")

    if os.path.exists("test_output.pdf"):
        print("Test PDF created successfully.")
        # Test extract_text
        text = sm.execute("pdf", "extract_text", file_path="test_output.pdf")
        print(f"Extracted Text: {text}")
        os.remove("test_output.pdf")
    else:
        print("Test PDF creation failed.")

def test_docx_skill():
    sm = SkillManager()
    sm.load_skills()

    # Test create action
    result = sm.execute("docx", "create", title="Test Doc", content="This is a test document.", output="test_output.docx")
    print(f"Docx Create Result: {result}")

    if os.path.exists("test_output.docx"):
        print("Test Docx created successfully.")
        # Test read action
        text = sm.execute("docx", "read", file_path="test_output.docx")
        print(f"Read Content: {text}")
        os.remove("test_output.docx")
    else:
        print("Test Docx creation failed.")

if __name__ == "__main__":
    print("Testing PDF Skill...")
    test_pdf_skill()
    print("\nTesting Docx Skill...")
    test_docx_skill()
