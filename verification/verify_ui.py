import os
from playwright.sync_api import sync_playwright

def run_verification(page):
    # Since we can't easily start the whole Butler app (which requires multiple dependencies and maybe hardware emulation)
    # We will verify the frontend by opening the index.html directly.
    current_dir = os.getcwd()
    file_url = f"file://{current_dir}/frontend/index.html"

    print(f"Opening {file_url}")
    page.goto(file_url)
    page.wait_for_timeout(2000)

    # 1. Take initial screenshot (Chat View)
    page.screenshot(path="verification/screenshots/chat_view.png")
    print("Saved chat_view.png")

    # 2. Switch to Time Machine View (1, 0)
    page.click("#dock-1-0", force=True)
    page.wait_for_timeout(2000) # wait for transition to settle
    page.screenshot(path="verification/screenshots/terminal_view.png") # Match old filename for compatibility
    print("Saved terminal_view.png")

    # 3. Switch to DAG Workflow View (0, 1)
    page.click("#dock-0-1", force=True)
    page.wait_for_timeout(2000) # wait for transition to settle
    page.screenshot(path="verification/screenshots/workspace_view.png") # Match old filename for compatibility
    print("Saved workspace_view.png")

    # 4. Switch to Skills & Files View (1, 1)
    page.click("#dock-1-1", force=True)
    page.wait_for_timeout(2000) # wait for transition to settle
    page.screenshot(path="verification/screenshots/files_view.png") # Match old filename for compatibility
    print("Saved files_view.png")

    # 5. Switch back to Chat View (0, 0) and simulate command input
    page.click("#dock-0-0", force=True)
    page.wait_for_timeout(2000) # wait for transition to settle

    # Simulate typing and sending via element text assignment
    page.evaluate("document.getElementById('chat-input').innerText = 'Hello Butler, show me the system quota.'")
    page.wait_for_timeout(500)
    page.click("#send-command-btn", force=True)
    page.wait_for_timeout(1000)

    page.screenshot(path="verification/screenshots/final_state.png")
    print("Saved final_state.png")

if __name__ == "__main__":
    os.makedirs("verification/screenshots", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        try:
            run_verification(page)
        finally:
            context.close()
            browser.close()
