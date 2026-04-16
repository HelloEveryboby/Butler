from playwright.sync_api import sync_playwright
import os
import time
import subprocess

def run_verification():
    # Start the app in the background
    process = subprocess.Popen(["python3", "verification/run_notifier_verification.py"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for the app to start (pywebview takes a bit)
    # Note: Modern UI runs on a random port or we need to find it.
    # Actually, ModernBridge uses webview.start() which blocks.
    # We might need to modify modern_app.py to accept a port or use a known one if it's a server.
    # But wait, modern_app.py uses pywebview which is a desktop window.
    # Playwright cannot easily test pywebview windows.
    # However, we can test the index.html directly if we serve it.

    # Let's serve the frontend/view directory
    serve_proc = subprocess.Popen(["python3", "-m", "http.server", "8000"], cwd="frontend/view")
    time.sleep(2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                record_video_dir="verification/videos"
            )
            page = context.new_page()

            # 1. Load the page
            page.goto("http://localhost:8000")
            page.wait_for_timeout(1000)

            # 2. Mock a notification push (since we are just serving static files)
            print("Mocking Notification Push via JS...")
            page.evaluate("""
                window.onNotificationPush({
                    id: 'notif_test_1',
                    title: '测试提醒 (Toast)',
                    content: '这是一条普通的低优先级测试提醒。',
                    priority: 1,
                    timestamp: '2024-05-22 10:00:00'
                });
            """)
            page.wait_for_timeout(2000)
            page.screenshot(path="verification/screenshots/toast_notif.png")

            # 3. Mock a high priority notification
            page.evaluate("""
                window.onNotificationPush({
                    id: 'notif_test_2',
                    title: '核心警报 (Fullscreen)',
                    content: '检测到核心系统异常，请立即检查！',
                    priority: 2,
                    timestamp: '2024-05-22 10:00:05'
                });
            """)
            page.wait_for_timeout(2000)
            page.screenshot(path="verification/screenshots/fullscreen_notif.png")

            # 4. Close notification
            page.click("text=确认并关闭")
            page.wait_for_timeout(1000)
            page.screenshot(path="verification/screenshots/after_close.png")

            context.close()
            browser.close()
    finally:
        serve_proc.terminate()
        process.terminate()

if __name__ == "__main__":
    run_verification()
