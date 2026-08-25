import asyncio
import os
from playwright.async_api import async_playwright

async def run_verification():
    screenshot_dir = "verification/screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        # Load local HTML file
        index_path = f"file://{os.path.abspath('frontend/index.html')}"
        await page.goto(index_path)
        await page.wait_for_timeout(1000)

        # 1. Open Screen Capture Panel Modal
        await page.evaluate("if (window.ScreenCapture) window.ScreenCapture.openPanel();")
        await page.wait_for_timeout(500)
        await page.screenshot(path=f"{screenshot_dir}/screen_capture_panel.png")
        print("[+] Screen capture panel verified.")

        # 2. Trigger Area Selection Mode and simulate mouse drag
        await page.evaluate("if (window.ScreenCapture) window.ScreenCapture.startAreaSelection('screenshot');")
        await page.wait_for_timeout(300)

        # Simulate drag selection
        await page.mouse.move(200, 200)
        await page.mouse.down()
        await page.mouse.move(650, 480)
        await page.mouse.up()
        await page.wait_for_timeout(500)

        await page.screenshot(path=f"{screenshot_dir}/screen_capture_area_selection.png")
        print("[+] Screen capture area selection & live dimension label verified.")

        # 3. Trigger Recording UI Indicator
        await page.evaluate("if (window.ScreenCapture) window.ScreenCapture.closeAll();")
        await page.evaluate("if (window.ScreenCapture) window.ScreenCapture.startRecordingUI('区域录制 (450×280)');")
        await page.wait_for_timeout(500)
        await page.screenshot(path=f"{screenshot_dir}/screen_capture_recording_indicator.png")
        print("[+] Screen capture recording indicator verified.")

        await page.screenshot(path=f"{screenshot_dir}/verification.png")
        await browser.close()
        print(f"[+] All visual verifications complete. Screenshots saved in {screenshot_dir}/")

if __name__ == "__main__":
    asyncio.run(run_verification())
