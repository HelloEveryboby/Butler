import os
from playwright.sync_api import sync_playwright

def run_verification(page):
    # Since we can't easily start the whole Butler app (which requires multiple dependencies and maybe hardware emulation)
    # We will verify the frontend by opening the index.html directly.
    current_dir = os.getcwd()
    file_url = f"file://{current_dir}/frontend/view/index.html"

    print(f"Opening {file_url}")
    page.goto(file_url)
    page.wait_for_timeout(1000)

    # 1. Take initial screenshot (Chat View)
    page.screenshot(path="verification/screenshots/chat_view.png")
    print("Saved chat_view.png")

    # 2. Switch to Terminal View
    page.click("#nav-terminal")
    page.wait_for_timeout(500)
    page.screenshot(path="verification/screenshots/terminal_view.png")
    print("Saved terminal_view.png")

    # 3. Switch to Workspace View
    page.click("#nav-workspace")
    page.wait_for_timeout(500)
    page.screenshot(path="verification/screenshots/workspace_view.png")
    print("Saved workspace_view.png")

    # 4. Switch to Files View
    page.click("#nav-files")
    page.wait_for_timeout(500)
    page.screenshot(path="verification/screenshots/files_view.png")
    print("Saved files_view.png")

    # 5. Switch to Settings View
    page.click("#nav-settings")
    page.wait_for_timeout(500)
    page.screenshot(path="verification/screenshots/settings_view.png")
    print("Saved settings_view.png")

    # 6. Go back to Chat and simulate a message
    page.click("#nav-chat")
    page.wait_for_timeout(500)

    # Simulate typing and sending
    page.fill("#chat-input", "Hello Butler, show me the system quota.")
    page.wait_for_timeout(500)
    page.click("#send-command-btn")
    page.wait_for_timeout(1000)

    page.screenshot(path="verification/screenshots/final_state.png")
    print("Saved final_state.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="verification/videos",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        try:
            run_verification(page)
        finally:
            context.close()
            browser.close()
