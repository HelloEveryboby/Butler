from playwright.sync_api import sync_playwright
import os

def run_verification(page):
    # Setup
    page.goto("http://localhost:8080/index.html")
    page.wait_for_timeout(2000) # Wait for all JS to load

    # 1. Show the modal
    # The button was added to .input-actions-left
    trigger_btn = page.locator('.input-actions-left button[title="触发确认框"]')
    trigger_btn.click()
    page.wait_for_timeout(1000)

    # Take screenshot of the modal
    page.screenshot(path="verification/screenshots/modal_shown.png")

    # 2. Confirm the action
    allow_btn = page.locator('.modal-btn-allow')
    allow_btn.click()
    page.wait_for_timeout(500)

    # Take screenshot of the toast
    page.screenshot(path="verification/screenshots/toast_shown.png")
    page.wait_for_timeout(2500) # Wait for mock loading and second toast

    page.screenshot(path="verification/screenshots/final_state.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    os.makedirs("verification/screenshots", exist_ok=True)
    os.makedirs("verification/videos", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="verification/videos"
        )
        page = context.new_page()
        try:
            run_verification(page)
        finally:
            context.close()
            browser.close()
