import os
import sys
import time
from playwright.sync_api import sync_playwright

def run_cuj(page):
    # Navigate to the local document studio server
    page.goto("http://127.0.0.1:8011")
    page.wait_for_timeout(1000)

    # Click the "实时预览" (Live Preview) tab
    page.get_by_role("button", name="实时预览").click()
    page.wait_for_timeout(1000)

    # Click back to "编辑" (Edit) tab
    page.get_by_role("button", name="编辑").click()
    page.wait_for_timeout(500)

    # Fill title and author
    page.locator("#doc-title").fill("Butler Security Audit Report")
    page.wait_for_timeout(500)
    page.locator("#doc-author").fill("Agent Jules")
    page.wait_for_timeout(500)

    # Select Cyberpunk Dark theme
    page.locator("#doc-theme").select_option("dark")
    page.wait_for_timeout(500)

    # Toggle theme on top right header
    page.locator("#theme-toggle").click()
    page.wait_for_timeout(1000)

    # Take screenshot of the gorgeous glassmorphic workspace
    os.makedirs("/home/jules/verification/screenshots", exist_ok=True)
    screenshot_path = "/home/jules/verification/screenshots/document_studio.png"
    page.screenshot(path=screenshot_path)
    print(f"[+] Visually verified and screenshot captured at {screenshot_path}")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="/home/jules/verification/videos"
        )
        page = context.new_page()
        try:
            run_cuj(page)
        finally:
            context.close()
            browser.close()
