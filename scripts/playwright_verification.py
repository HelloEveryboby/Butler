import os
from playwright.sync_api import sync_playwright

def run_cuj(page):
    index_path = f"file://{os.path.abspath('frontend/index.html')}"
    page.goto(index_path)
    page.wait_for_timeout(500)

    # 1. Open Screen Capture Panel Modal
    page.evaluate("if (window.ScreenCapture) window.ScreenCapture.openPanel();")
    page.wait_for_timeout(500)

    # 2. Trigger Area Selection
    page.evaluate("if (window.ScreenCapture) window.ScreenCapture.startAreaSelection('screenshot');")
    page.wait_for_timeout(300)

    # Drag select
    page.mouse.move(200, 200)
    page.mouse.down()
    page.mouse.move(650, 480)
    page.mouse.up()
    page.wait_for_timeout(500)

    # Take screenshot at the final state
    screenshot_path = "/home/jules/verification/screenshots/verification.png"
    page.screenshot(path=screenshot_path)
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
        finally:
            context.close()
            browser.close()
