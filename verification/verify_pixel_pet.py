import os
import time
from playwright.sync_api import sync_playwright

def verify_pet_page(page):
    current_dir = os.getcwd()
    pet_html = f"file://{current_dir}/skills/pixel_pet/ui/index.html"
    print(f"Opening Pixel Pet: {pet_html}")
    page.goto(pet_html)
    page.wait_for_timeout(1000)

    # 1. Take initial screenshot of Widget Mode
    os.makedirs("verification/screenshots", exist_ok=True)
    page.screenshot(path="verification/screenshots/pet_widget_mode.png")
    print("Saved pet_widget_mode.png")

    # 2. Click the dialogue bubble to expand to Panel Mode
    page.click("#pet-dialog")
    page.wait_for_timeout(1000)
    page.screenshot(path="verification/screenshots/pet_panel_mode.png")
    print("Saved pet_panel_mode.png")

    # 3. Try clicking mood buttons
    page.click("button[data-mood='happy']")
    page.wait_for_timeout(1000)
    page.screenshot(path="verification/screenshots/pet_mood_happy.png")
    print("Saved pet_mood_happy.png")

    # 4. Collapse back to Widget Mode
    page.click("#btn-collapse")
    page.wait_for_timeout(1000)
    page.screenshot(path="verification/screenshots/pet_collapsed.png")
    print("Saved pet_collapsed.png")

def verify_frontend_settings(page):
    current_dir = os.getcwd()
    frontend_html = f"file://{current_dir}/frontend/index.html"
    print(f"Opening Butler Main Frontend: {frontend_html}")

    # Bypass onboarding tour via localStorage
    page.goto(frontend_html)
    page.evaluate("localStorage.setItem('butler_onboarding_completed', 'true')")
    page.reload()
    page.wait_for_timeout(1500)

    # Open settings overlay (toggleSettings)
    page.evaluate("window.toggleSettings()")
    page.wait_for_timeout(500)

    # Switch to "界面与主题" (Theme settings) tab
    page.click("#tab-btn-theme-config")
    page.wait_for_timeout(500)

    # Take a screenshot to show the new "桌面电子小狗 (Pixel Pet)" button
    page.screenshot(path="verification/screenshots/butler_settings_pixel_pet.png")
    print("Saved butler_settings_pixel_pet.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Record video of our interactions!
        os.makedirs("verification/videos", exist_ok=True)
        context = browser.new_context(
            record_video_dir="verification/videos",
            viewport={'width': 1024, 'height': 768}
        )
        page = context.new_page()
        try:
            verify_pet_page(page)
            verify_frontend_settings(page)
        finally:
            context.close()
            browser.close()
        print("Frontend Verification Completed Successfully.")
