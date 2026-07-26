import sys
import subprocess
import time
from playwright.sync_api import sync_playwright

def run_verification():
    # Start local http server in the background
    server_process = subprocess.Popen(
        [sys.executable, "-m", "http.server", "3000", "--directory", "frontend"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2)  # Give server time to spin up

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                record_video_dir="/home/jules/verification/videos",
                viewport={"width": 1280, "height": 900}
            )
            page = context.new_page()

            # Navigate to local dev server
            page.goto("http://localhost:3000/index.html")
            page.wait_for_timeout(1000)

            # Skip onboarding first
            page.evaluate("if (typeof skipOnboarding === 'function') skipOnboarding();")
            page.wait_for_timeout(500)

            # Trigger opening of Memos overlay
            page.evaluate("toggleMemos()")
            page.wait_for_timeout(1000)

            # Inject Mock Memos into window.memosManager to simulate PyWebView database load
            mock_memos_js = """
            const mockMemos = [
                {
                    id: 1,
                    content: "📌 项目灵感：AI 边缘应用\\n结合 LiteRT 和 Gemini Nano，构建一个完全离线的智能助手...",
                    tags: ["#创意", "#AI", "#边缘计算"],
                    resources: [],
                    created_at: 1785052800,
                    is_pinned: 1,
                    is_archived: 0
                },
                {
                    id: 2,
                    content: "📝 读书笔记：《设计中的设计》\\n原研哉对“白”的诠释——不是颜色，而是一种感知的留白...",
                    tags: ["#阅读", "#设计", "#哲学"],
                    resources: [],
                    created_at: 1784966400,
                    is_pinned: 0,
                    is_archived: 0
                },
                {
                    id: 3,
                    content: "🛒 购物清单\\n牛奶、鸡蛋、全麦面包、蓝莓、希腊酸奶...",
                    tags: ["#生活", "#采购", "#待办"],
                    resources: [],
                    created_at: 1784880000,
                    is_pinned: 0,
                    is_archived: 0
                },
                {
                    id: 4,
                    content: "💡 周报要点\\n完成模型量化实验，准确率提升 2.1%；与产品团队同步下季度计划...",
                    tags: ["#工作", "#汇报", "#进行中"],
                    resources: [],
                    created_at: 1784793600,
                    is_pinned: 0,
                    is_archived: 0
                }
            ];

            const mgr = window.memosManager;
            if (mgr) {
                mgr.currentMemos = mockMemos;
                mgr.pinnedMemos = mockMemos.filter(m => m.is_pinned === 1 && m.is_archived === 0);
                mgr.unpinnedMemos = mockMemos.filter(m => m.is_pinned === 0 && m.is_archived === 0);
                mgr.archivedMemos = mockMemos.filter(m => m.is_archived === 1);
                mgr.renderCurrentView();
            }
            """
            page.evaluate(mock_memos_js)
            page.wait_for_timeout(1000)

            # Take a high-quality screenshot of the memos workspace list
            page.screenshot(path="/home/jules/verification/screenshots/memos_workspace_mock.png")
            print("Screenshot with mock memos taken successfully!")

            # Click select button to show checkboxes and selection mode
            page.click("#select-memos-btn")
            page.wait_for_timeout(1000)

            # Click actual checkboxes in the DOM
            checkboxes = page.locator(".card-checkbox")
            if checkboxes.count() > 0:
                checkboxes.nth(0).click()
                page.wait_for_timeout(500)
                checkboxes.nth(1).click()
                page.wait_for_timeout(500)

            # Take another screenshot of selection mode
            page.screenshot(path="/home/jules/verification/screenshots/memos_selection_mode.png")
            print("Screenshot in selection mode taken successfully!")

            context.close()
            browser.close()
    finally:
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    run_verification()
