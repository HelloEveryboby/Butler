import os
import sys
import time
from playwright.sync_api import sync_playwright

def run_cuj(page):
    # Navigate to the standalone downloader UI
    print("Navigating to http://localhost:8329/ui/index.html...")
    page.goto("http://localhost:8329/ui/index.html")
    page.wait_for_timeout(1000)

    # Verify elements
    print("Verifying Standalone Badge is visible...")
    badge_visible = page.is_visible("#standalone-badge")
    print(f"Standalone Badge visible: {badge_visible}")

    print("Verifying 'Back to Home' button is hidden...")
    back_visible = page.is_visible("#btn-back-home")
    print(f"'Back to Home' button visible: {back_visible}")

    # Go to Settings
    print("Clicking on '设置中心' (Settings Center)...")
    page.click("#tab-settings")
    page.wait_for_timeout(800)

    # Focus on path setting and input a custom path
    print("Entering custom download save path...")
    page.fill("#settings-downloadpath", "/home/jules/Downloads/CustomStore")
    page.wait_for_timeout(500)

    # Click Save Settings
    print("Clicking '保存设置' (Save Settings)...")
    page.get_by_role("button", name="保存设置").click()
    page.wait_for_timeout(1500) # Wait for toast message to pop up and hold

    # Take screenshot at the final state
    screenshot_path = "/home/jules/verification/screenshots/verification.png"
    page.screenshot(path=screenshot_path)
    print(f"Screenshot successfully saved to {screenshot_path}")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    os.makedirs("/home/jules/verification/videos", exist_ok=True)
    os.makedirs("/home/jules/verification/screenshots", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="/home/jules/verification/videos"
        )
        page = context.new_page()
        try:
            run_cuj(page)
        except Exception as e:
            print(f"Error executing CUJ: {e}")
        finally:
            context.close()
            browser.close()
