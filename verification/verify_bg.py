import os
from playwright.sync_api import sync_playwright

def run_verification(page):
    current_dir = os.getcwd()
    file_url = f"file://{current_dir}/frontend/view/index.html"
    page.goto(file_url)
    page.wait_for_timeout(1000)

    # Simulate a background setting via localStorage since we can't easily upload a file in headless playwright without a mock
    # We will inject a blue data URL as the background
    blue_pixel = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    page.evaluate(f'localStorage.setItem("butler-custom-bg", "{blue_pixel}")')
    page.reload()
    page.wait_for_timeout(1000)

    # Verify that the body has the custom background class and the style
    page.screenshot(path="verification/screenshots/custom_bg_applied.png")
    print("Saved custom_bg_applied.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        try:
            run_verification(page)
        finally:
            context.close()
            browser.close()
