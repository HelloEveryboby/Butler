from playwright.sync_api import sync_playwright
import os
import time

def run_verification():
    screenshot_dir = "assets/ui_screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    with sync_playwright() as p:
        # We'll use file path since it's a static frontend file
        current_dir = os.getcwd()
        file_path = f"file://{current_dir}/frontend/view/index.html"

        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})

        print(f"Opening {file_path}")
        page.goto(file_path)

        # Wait for some initial animations or JS to run
        time.sleep(2)

        # Capture the main chat view
        page.screenshot(path=f"{screenshot_dir}/ui_chat.png")
        print("Captured ui_chat.png")

        # Switch to Terminal view
        page.click("#nav-terminal")
        time.sleep(1)
        page.screenshot(path=f"{screenshot_dir}/ui_terminal.png")
        print("Captured ui_terminal.png")

        # Switch to Workspace view
        page.click("#nav-workspace")
        time.sleep(1)
        page.screenshot(path=f"{screenshot_dir}/ui_workspace.png")
        print("Captured ui_workspace.png")

        # Switch to Files view
        page.click("#nav-files")
        time.sleep(1)
        page.screenshot(path=f"{screenshot_dir}/ui_files.png")
        print("Captured ui_files.png")

        # Switch to Settings view
        page.click("#nav-settings")
        time.sleep(1)
        page.screenshot(path=f"{screenshot_dir}/ui_settings.png")
        print("Captured ui_settings.png")

        browser.close()

if __name__ == "__main__":
    run_verification()
