import os
import asyncio
from playwright.async_api import async_playwright

async def run_verification():
    os.makedirs("verification/screenshots", exist_ok=True)
    os.makedirs("verification/videos", exist_ok=True)

    async with async_playwright() as p:
        # Launch Chromium headless browser
        browser = await p.chromium.launch(headless=True)
        # We can also record video of the complete journey!
        context = await browser.new_context(
            viewport={"width": 1200, "height": 800},
            record_video_dir="verification/videos"
        )
        page = await context.new_page()

        # Load the local Storage Hub index.html
        file_path = "file://" + os.path.abspath("skills/storage_hub/ui/index.html")
        print(f"Loading page: {file_path}")
        await page.goto(file_path)

        # 1. Wait for animations and take screenshot of onboarding spotlight
        await page.wait_for_timeout(1000)
        await page.screenshot(path="verification/screenshots/onboarding.png")
        print("Onboarding spotlight captured.")

        # 2. Click the start button on onboarding to dismiss it
        await page.click(".btn-onboard-next")
        await page.wait_for_timeout(500)
        await page.screenshot(path="verification/screenshots/empty_state.png")
        print("Empty state captured after dismissing onboarding.")

        # 3. Click the gear icon to open configuration modal
        await page.click("#config-gear-btn")
        await page.wait_for_timeout(500)
        await page.screenshot(path="verification/screenshots/config_modal.png")
        print("Config modal captured.")

        # 4. Fill in some WebDAV fields and submit the form to save config
        # By default, HTML form fields already have pre-populated values we wrote, so we can just submit!
        await page.click("#drive-config-form button[type='submit']")
        await page.wait_for_timeout(1000) # Wait for drives list loading animation
        await page.screenshot(path="verification/screenshots/workspace.png")
        print("Workspace loaded with drives captured.")

        # 5. Hover over the SVG circular quota ring to show segment chart details tooltip
        await page.hover("#quota-ring-container")
        await page.wait_for_timeout(500)
        await page.screenshot(path="verification/screenshots/quota_tooltip.png")
        print("Quota hover details tooltip captured.")

        # 6. Click on the AList WebDAV card to enter file explorer
        # Find the card with text "AList WebDAV"
        await page.click("text=AList WebDAV")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="verification/screenshots/file_list.png")
        print("File explorer view captured.")

        # 7. Click on action menu (vertical dots ⋮) to trigger local context message
        await page.click(".btn-icon-more >> nth=0")
        await page.wait_for_timeout(800)
        await page.screenshot(path="verification/screenshots/context_menu.png")
        print("Context menu context message captured.")

        # 8. Let's trigger cross-drive target chooser modal
        # We can simulate dropping a file or triggering the method directly
        await page.evaluate("ui.showTargetChooser({ name: 'Ubuntu_24.04_LTS.iso', sourceDrive: 'alist_webdav' })")
        await page.wait_for_timeout(500)
        await page.screenshot(path="verification/screenshots/target_chooser.png")
        print("Cross-drive target chooser modal captured.")

        # 9. Choose OneDrive to start asynchronous RAM-Pipe transfer simulation
        await page.click("text=传输到 Microsoft OneDrive")
        await page.wait_for_timeout(1000) # Wait for progress to start incrementing
        await page.screenshot(path="verification/screenshots/transferring.png")
        print("Transferring progress screen captured.")

        # 10. Wait for complete transfer status completed
        await page.wait_for_timeout(4000) # Wait for mock progress to hit 100%
        await page.screenshot(path="verification/screenshots/completed.png")
        print("Transfer completion screen captured.")

        # Take a final overall verification summary screenshot
        await page.screenshot(path="verification/screenshots/verification.png")

        await context.close()
        await browser.close()
        print("Visual verification successfully completed! Screenshots are in verification/screenshots/, videos are in verification/videos/.")

if __name__ == "__main__":
    asyncio.run(run_verification())
