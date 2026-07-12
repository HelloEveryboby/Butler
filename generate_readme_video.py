import os
import time
import asyncio
from playwright.async_api import async_playwright

async def generate_video():
    os.makedirs("assets", exist_ok=True)
    os.makedirs("verification/videos", exist_ok=True)

    current_dir = os.getcwd()
    frontend_url = f"file://{current_dir}/frontend/index.html"
    storage_hub_url = f"file://{current_dir}/skills/storage_hub/ui/index.html"

    print("Starting Playwright for README presentation video...")
    async with async_playwright() as p:
        # Launch headless Chromium
        browser = await p.chromium.launch(headless=True)
        # Record video inside context with specific standard size (1280x800) and video size
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_size={"width": 1280, "height": 800},
            record_video_dir="verification/videos"
        )
        page = await context.new_page()

        # ==========================================
        # PART 1: Modern 2x2 Matrix UI Dashboard
        # ==========================================
        print(f"Loading Butler Dashboard: {frontend_url}")
        await page.goto(frontend_url)
        await page.wait_for_timeout(2500)  # Wait for landing heatmap and UI elements to load

        # 1. Simulate user typing a request in the Chat input
        print("Simulating user chat command...")
        await page.click("#chat-input")
        await page.keyboard.type("你好, Butler! 开启 2x2 玻璃拟态矩阵并进行系统自检。", delay=40)
        await page.wait_for_timeout(400)
        await page.evaluate("document.getElementById('send-command-btn').click()")
        await page.wait_for_timeout(1500)

        # 2. Transition to Time Machine view (1,0)
        print("Transitioning to Time Machine view...")
        await page.evaluate("matrix.moveTo(1, 0)")
        await page.wait_for_timeout(1200)
        # Move the Time Machine slider to show history rewind simulation
        await page.evaluate("document.getElementById('global-tm-slider').value = 45; document.getElementById('global-tm-slider').dispatchEvent(new Event('input'))")
        await page.wait_for_timeout(1500)

        # 3. Transition to DAG Pipeline view (0,1)
        print("Transitioning to DAG Pipeline canvas...")
        await page.evaluate("matrix.moveTo(0, 1)")
        await page.wait_for_timeout(2000)  # Allow spring physics and glowing connections to animate

        # 4. Transition to Skills & Files view (1,1)
        print("Transitioning to Skills & Files view...")
        await page.evaluate("matrix.moveTo(1, 1)")
        await page.wait_for_timeout(1200)

        # Open Overlay Terminal in Skills view
        print("Opening overlay terminal...")
        await page.evaluate("toggleTerminal()")
        await page.wait_for_timeout(1000)
        # Write simulated commands to xterm.js terminal instance
        await page.evaluate("if (window.term) { window.term.write('butler --version\\r\\n\\u001b[32mBUTLER v2.0.0 [Local-First Architecture]\\u001b[0m\\r\\n\\r\\n$ ') }")
        await page.wait_for_timeout(1000)
        # Close terminal
        await page.evaluate("toggleTerminal()")
        await page.wait_for_timeout(800)

        # Open Memo transparent overlays
        print("Opening Memo overlays...")
        await page.evaluate("toggleMemos()")
        await page.wait_for_timeout(1200)
        # Close Memo overlays
        await page.evaluate("toggleMemos()")
        await page.wait_for_timeout(800)

        # 5. Trigger Copilot Glassmorphic Confirmation Dialog
        print("Triggering Copilot security dialog...")
        # Hover/click the shield-check button in input area
        await page.evaluate("matrix.moveTo(0, 0)")  # Move back to Chat quadrant first
        await page.wait_for_timeout(1500)  # Wait for matrix transition to stabilize completely
        await page.evaluate("document.querySelector('.fa-shield-check').click()")
        await page.wait_for_timeout(1500)  # Modal scale-up and backdrop blur animation

        # Click Allow in modal
        print("Approving copilot task...")
        await page.evaluate("document.querySelector('.modal-btn-allow').click()")
        await page.wait_for_timeout(2500)  # Toast triggers and simulated refactoring completes

        # ==========================================
        # PART 2: Local-First Storage Hub UI
        # ==========================================
        print(f"Loading Storage Hub Interface: {storage_hub_url}")
        await page.goto(storage_hub_url)
        await page.wait_for_timeout(1500)

        # Dismiss onboarding spotlight
        print("Dismissing Storage Hub onboarding...")
        await page.evaluate("document.querySelector('.btn-onboard-next').click()")
        await page.wait_for_timeout(800)

        # Open config modal
        print("Opening Storage Hub config...")
        await page.evaluate("document.getElementById('config-gear-btn').click()")
        await page.wait_for_timeout(1000)

        # Save config & load drives workspace
        print("Saving drives workspace...")
        await page.evaluate("document.querySelector('#drive-config-form button[type=\"submit\"]').click()")
        await page.wait_for_timeout(1500)

        # Hover quota ring details
        print("Showing quota ring details tooltip...")
        await page.hover("#quota-ring-container")
        await page.wait_for_timeout(1000)

        # Open WebDAV card explorer
        print("Opening WebDAV file explorer...")
        await page.evaluate("document.querySelectorAll('.drive-card')[0].click()") # Click the first drive card
        await page.wait_for_timeout(1500)

        # Trigger Context actions
        print("Opening file actions menu...")
        await page.evaluate("document.querySelector('.btn-icon-more').click()")
        await page.wait_for_timeout(1000)

        # Trigger Cross-Drive Transfer popup
        print("Triggering cross-drive target chooser...")
        await page.evaluate("ui.showTargetChooser({ name: 'Ubuntu_24.04_LTS.iso', sourceDrive: 'alist_webdav' })")
        await page.wait_for_timeout(1200)

        # Initiate Transfer
        print("Initiating Microsoft OneDrive transfer...")
        await page.evaluate("document.querySelector('.target-drv-btn').click()") # Click OneDrive option
        await page.wait_for_timeout(3500)  # Wait for progress bar to increment and hit completed state

        # Final pause
        await page.wait_for_timeout(1000)

        # Close browser context to finalize the video
        await context.close()
        await browser.close()
        print("Playwright recording completed successfully!")

if __name__ == "__main__":
    asyncio.run(generate_video())
