import os
import sys
from playwright.sync_api import sync_playwright

def run_cuj(page):
    # Load index.html locally directly using file:// protocol
    html_path = os.path.abspath("frontend/index.html")
    page.goto(f"file://{html_path}")
    page.wait_for_timeout(1000)

    # Skip onboarding tour overlay if active
    page.evaluate("if(window.skipOnboarding) { window.skipOnboarding(); }")
    page.wait_for_timeout(1000)

    # Open the Skills Manager directly by evaluating its toggle function
    page.evaluate("if(window.toggleSkillsManager) { window.toggleSkillsManager(); }")
    page.wait_for_timeout(1500)

    # Click on the Filter Tabs to demonstrate interactivity via JS triggers
    page.evaluate("if(window.skillsManager) { window.skillsManager.setFilter('builtin'); }")
    page.wait_for_timeout(500)

    page.evaluate("if(window.skillsManager) { window.skillsManager.setFilter('external'); }")
    page.wait_for_timeout(500)

    page.evaluate("if(window.skillsManager) { window.skillsManager.setFilter('all'); }")
    page.wait_for_timeout(500)

    # Fill out the Custom Skill installation fields with mock content using DOM directly
    page.evaluate("""
        document.getElementById('install-skill-url').value = 'https://github.com/butler-ai/skill-example.git';
        document.getElementById('install-skill-name').value = '演示穿搭扩展';
    """)
    page.wait_for_timeout(500)

    # Trigger mock installation via direct evaluate call
    page.evaluate("if(window.skillsManager) { window.skillsManager.installSkill(); }")
    page.wait_for_timeout(2500) # Wait for mock installation timeout (1800ms)

    # Take screenshot of the complete interactive Skills Management Overlay UI
    page.screenshot(path="/home/jules/verification/screenshots/verification.png")
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
