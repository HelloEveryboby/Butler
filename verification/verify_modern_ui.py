from playwright.sync_api import sync_playwright

def run_cuj(page):
    # Navigate to the static dashboard HTML directly
    import os
    path = "file://" + os.path.abspath("frontend/index.html")
    page.goto(path)
    page.wait_for_timeout(1000)

    # 1. Trigger stream typist simulated chunks
    page.evaluate("""() => {
        window.onAIStreamStart();
        window.onAIStreamChunk("报告长官，已将所有系统模块完美升级。");
        window.onAIStreamChunk(" 背景已完美流体化，霓虹尾巴已点亮！");
        window.onAIStreamEnd();
    }""")
    page.wait_for_timeout(1000)

    # 2. Simulate Dreaming start
    page.evaluate("""() => {
        window.updateDreamingState(true);
    }""")
    page.wait_for_timeout(1500)

    # 3. Simulate Quota Exhaustion
    page.evaluate("""() => {
        window.updateQuotaExhaustedState(true);
    }""")
    page.wait_for_timeout(1000)

    # Take screenshot at the key moment showing the beautiful glassmorphism elements, fluid bubbles and indicators
    page.screenshot(path="/home/jules/verification/screenshots/verification.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
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
