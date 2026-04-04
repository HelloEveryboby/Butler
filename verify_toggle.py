import os
from playwright.sync_api import sync_playwright

def run_verification(page):
    current_dir = os.getcwd()
    file_url = f"file://{current_dir}/frontend/view/index.html"
    page.goto(file_url)
    page.wait_for_timeout(1000)

    # 1. Take initial screenshot with sidebar visible
    page.screenshot(path="verification/screenshots/sidebar_visible.png")
    print("Saved sidebar_visible.png")

    # 2. Click the toggle button to hide the sidebar
    page.click("#sidebar-toggle")
    page.wait_for_timeout(1000) # Wait for animation
    page.screenshot(path="verification/screenshots/sidebar_hidden.png")
    print("Saved sidebar_hidden.png")

    # 3. Reload the page to test persistence
    page.reload()
    page.wait_for_timeout(1000)
    page.screenshot(path="verification/screenshots/persistence_check.png")
    print("Saved persistence_check.png")

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
