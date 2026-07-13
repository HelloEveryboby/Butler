import os
import time
from playwright.sync_api import sync_playwright

def run_verification():
    screenshot_dir = "assets/ui_screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    with sync_playwright() as p:
        current_dir = os.getcwd()
        file_path = f"file://{current_dir}/frontend/index.html"

        # Launch Chromium
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        print(f"Opening local Butler index.html at: {file_path}")
        page.goto(file_path)
        time.sleep(1)

        # Clear localStorage and reload to ensure Onboarding runs fresh
        page.evaluate("localStorage.clear();")
        page.reload()
        print("Reloaded page with cleared localStorage. Starting Onboarding Tour...")
        time.sleep(2)

        # 1. Capture Onboarding Step 1 (Smart Chat (0,0))
        page.screenshot(path=f"{screenshot_dir}/pm_onboarding_step1.png")
        print("Captured pm_onboarding_step1.png")

        # 2. Click Next on onboarding bubble to go to Step 2 (Time Machine (1,0))
        page.click("#onboarding-next-btn")
        time.sleep(1.5)
        page.screenshot(path=f"{screenshot_dir}/pm_onboarding_step2.png")
        print("Captured pm_onboarding_step2.png")

        # 3. Click Next to go to Step 3 (DAG Canvas (0,1))
        page.click("#onboarding-next-btn")
        time.sleep(1.5)
        page.screenshot(path=f"{screenshot_dir}/pm_onboarding_step3.png")
        print("Captured pm_onboarding_step3.png")

        # 4. Click Next to go to Step 4 (Skills & Files (1,1))
        page.click("#onboarding-next-btn")
        time.sleep(1.5)
        page.screenshot(path=f"{screenshot_dir}/pm_onboarding_step4.png")
        print("Captured pm_onboarding_step4.png")

        # 5. Click Finish Onboarding
        page.click("#onboarding-next-btn")
        time.sleep(1)
        print("Finished onboarding tour.")

        # 6. Click the Settings gear in Floating Dock to trigger the Settings Overlay
        page.click("#dock-settings")
        time.sleep(1)
        page.screenshot(path=f"{screenshot_dir}/pm_settings_panel.png")
        print("Captured pm_settings_panel.png")

        # 7. Switch Settings Tab to '记忆库管理'
        page.click("#tab-btn-memory-config")
        time.sleep(0.5)
        page.screenshot(path=f"{screenshot_dir}/pm_settings_memory_tab.png")
        print("Captured pm_settings_memory_tab.png")

        # 8. Switch Settings Tab to '系统与硬件 HAL'
        page.click("#tab-btn-hal-status")
        time.sleep(0.5)
        page.screenshot(path=f"{screenshot_dir}/pm_settings_hal_tab.png")
        print("Captured pm_settings_hal_tab.png")

        # 9. Switch Settings Tab to '界面与主题' and toggle Theme input
        page.click("#tab-btn-theme-config")
        time.sleep(0.5)
        page.click("#setting-theme-toggle + .slider")
        time.sleep(1)
        page.screenshot(path=f"{screenshot_dir}/pm_settings_theme_tab_dark.png")
        print("Captured pm_settings_theme_tab_dark.png")

        # Close settings
        page.click("#settings-overlay .panel-header button")
        time.sleep(0.5)
        page.screenshot(path=f"{screenshot_dir}/pm_dark_theme_matrix_chat.png")
        print("Captured pm_dark_theme_matrix_chat.png")

        # 10. Go to DAG Canvas, drag a skill card and drop it onto the canvas to test DAG controls
        # Let's move to DAG Canvas first
        page.evaluate("window.matrix.moveTo(0, 1);")
        time.sleep(1)

        # Drag and Drop mock node
        # In skills drawer, let's select the first skill card
        page.evaluate("""() => {
            const drawer = document.getElementById('skills-drawer');
            if (drawer) {
                // Manually trigger onDrop simulating a skill drop
                const dragEventData = {
                    type: 'skill',
                    name: '系统自愈分析器',
                    icon: 'fa-microchip'
                };
                const mockEvent = {
                    preventDefault: () => {},
                    clientX: 300,
                    clientY: 300,
                    dataTransfer: {
                        getData: (format) => format === 'application/json' ? JSON.stringify(dragEventData) : ''
                    }
                };
                window.dagEngine.onDrop(mockEvent);
            }
        }""")
        time.sleep(0.5)

        # Now trigger '启动' inside DAG Toolbar to trigger flows and status badges
        page.evaluate("window.runDagPipeline();")
        time.sleep(1)
        page.screenshot(path=f"{screenshot_dir}/pm_dag_running_glow.png")
        print("Captured pm_dag_running_glow.png")

        browser.close()

if __name__ == "__main__":
    run_verification()
