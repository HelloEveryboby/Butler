import os
from playwright.sync_api import sync_playwright

def run_cuj(page):
    current_dir = os.getcwd()
    file_path = f"file://{current_dir}/frontend/index.html"
    print(f"Opening local frontend: {file_path}")
    page.goto(file_path)
    page.wait_for_timeout(1000)

    # Disable onboarding overlay to prevent intercepting clicks
    print("Disabling onboarding tour overlay...")
    page.evaluate("localStorage.setItem('butler_onboarding_completed', 'true')")
    page.goto(file_path)
    page.wait_for_timeout(1000)

    # 1. Take a screenshot of the initial desktop matrix view
    print("Capturing initial desktop view...")
    page.screenshot(path="/home/jules/verification/screenshots/1_desktop_init.png")
    page.wait_for_timeout(500)

    # 2. Click the settings cog in the dock to open settings overlay
    print("Opening Settings Overlay...")
    page.click("#dock-settings")
    page.wait_for_timeout(500)

    # 3. Switch to Interface & Theme config tab
    print("Switching to Interface & Theme settings tab...")
    page.click("#tab-btn-theme-config")
    page.wait_for_timeout(500)

    # Take a screenshot showing the settings panel with the new Operation Interface Mode selector
    print("Capturing settings panel view...")
    page.screenshot(path="/home/jules/verification/screenshots/2_settings_panel.png")
    page.wait_for_timeout(500)

    # 4. Change interface mode to Mobile Mode
    print("Selecting Mobile Mode (手机端界面)...")
    page.select_option("#setting-interface-mode", "mobile")
    # Wait for the smooth fade transition (0.3s)
    page.wait_for_timeout(1000)

    # 5. Close settings overlay
    print("Closing Settings Overlay...")
    page.evaluate("window.toggleSettings()")
    page.wait_for_timeout(1000)

    # Take a screenshot showing the simulated mobile screen container in the center of the desktop window
    print("Capturing simulated mobile device screen view...")
    page.screenshot(path="/home/jules/verification/screenshots/3_mobile_mode_simulated.png")
    page.wait_for_timeout(1000)

    print("Verification CUJ Completed Successfully!")

if __name__ == "__main__":
    # Create verification directories
    os.makedirs("/home/jules/verification/videos", exist_ok=True)
    os.makedirs("/home/jules/verification/screenshots", exist_ok=True)

    with sync_playwright() as p:
        # Launch browser with desktop viewport (e.g., 1440x900)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            record_video_dir="/home/jules/verification/videos"
        )
        page = context.new_page()
        try:
            run_cuj(page)
        finally:
            context.close()
            browser.close()
