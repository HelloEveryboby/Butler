import os
import time
import asyncio
from playwright.async_api import async_playwright

async def init_hud(page):
    await page.evaluate("""
        const style = document.createElement('style');
        style.innerHTML = `
            .demo-hud-panel {
                position: fixed;
                top: 25px;
                left: 50%;
                transform: translateX(-50%) translateY(-20px);
                z-index: 999999;
                background: rgba(255, 255, 255, 0.9);
                backdrop-filter: blur(25px);
                -webkit-backdrop-filter: blur(25px);
                border: 1px solid rgba(255, 255, 255, 0.7);
                border-radius: 16px;
                padding: 12px 28px;
                display: flex;
                align-items: center;
                gap: 18px;
                box-shadow: 0 12px 38px rgba(0, 0, 0, 0.12);
                font-family: 'Inter', -apple-system, 'SF Pro Display', sans-serif;
                color: #1d1d1f;
                transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
                opacity: 0;
                pointer-events: none;
            }
            .demo-hud-panel.visible {
                opacity: 1;
                transform: translateX(-50%) translateY(0);
            }
            .demo-hud-step {
                font-size: 14px;
                font-weight: 700;
                color: #007aff;
                background: rgba(0, 122, 255, 0.1);
                padding: 5px 12px;
                border-radius: 8px;
                white-space: nowrap;
            }
            .demo-hud-text {
                display: flex;
                flex-direction: column;
            }
            .demo-hud-title {
                font-size: 16px;
                font-weight: 600;
                letter-spacing: -0.2px;
            }
            .demo-hud-desc {
                font-size: 12px;
                color: #515154;
                margin-top: 3px;
                white-space: nowrap;
            }
        `;
        document.head.appendChild(style);

        const hud = document.createElement('div');
        hud.id = 'demo-hud';
        hud.className = 'demo-hud-panel';
        hud.innerHTML = `
            <div class="demo-hud-step" id="demo-hud-step">01</div>
            <div class="demo-hud-text">
                <div class="demo-hud-title" id="demo-hud-title">Title</div>
                <div class="demo-hud-desc" id="demo-hud-desc">Description</div>
            </div>
        `;
        document.body.appendChild(hud);
    """)

async def update_hud(page, step, title, desc):
    await page.evaluate(f"""
        const hud = document.getElementById('demo-hud');
        const stepEl = document.getElementById('demo-hud-step');
        const titleEl = document.getElementById('demo-hud-title');
        const descEl = document.getElementById('demo-hud-desc');

        hud.classList.remove('visible');
        setTimeout(() => {{
            stepEl.innerText = "{step}";
            titleEl.innerText = "{title}";
            descEl.innerText = "{desc}";
            hud.classList.add('visible');
        }}, 300);
    """)

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
        await page.wait_for_timeout(2000)
        await init_hud(page)
        await page.wait_for_timeout(1500)

        # Stage 1: Chat and Smart input
        # We give 4 seconds to comfortably read the step introduction before actions begin!
        await update_hud(page, "01 / 06", "智能助手与多模态排障 (0,0)", "支持智能输入联想、截图即排障与一键自愈修复流程")
        await page.wait_for_timeout(4000)

        print("Simulating user chat command...")
        await page.click("#chat-input")
        # Type slightly slower (80ms delay) so characters appear clearly and readability is high!
        await page.keyboard.type("你好, Butler! 开启 2x2 玻璃拟态矩阵并进行系统自检流程。", delay=80)
        await page.wait_for_timeout(1000)
        await page.evaluate("document.getElementById('send-command-btn').click()")
        await page.wait_for_timeout(3000) # Give 3s to read the command results and animations

        # Stage 2: Time Machine (1,0)
        await update_hud(page, "02 / 06", "全局可观测时光机 (1,0)", "影音级系统状态回溯，通过时间轴滑块重现系统历史快照")
        await page.wait_for_timeout(4000) # Give 4s to read

        print("Transitioning to Time Machine view...")
        await page.evaluate("matrix.moveTo(1, 0)")
        await page.wait_for_timeout(2500) # Wait for transition to complete
        # Move the Time Machine slider to show history rewind simulation
        await page.evaluate("document.getElementById('global-tm-slider').value = 45; document.getElementById('global-tm-slider').dispatchEvent(new Event('input'))")
        await page.wait_for_timeout(3000) # Wait to see the slider action clearly

        # Stage 3: DAG Pipeline (0,1)
        await update_hud(page, "03 / 06", "DAG 可视化任务流水线 (0,1)", "采用发光实体连接线与弹簧物理反馈，拖拽构建复杂任务流")
        await page.wait_for_timeout(4000) # Give 4s to read

        print("Transitioning to DAG Pipeline canvas...")
        await page.evaluate("matrix.moveTo(0, 1)")
        await page.wait_for_timeout(4000)  # Allow spring physics and glowing connections to animate beautifully

        # Stage 4: Skills and Files (1,1)
        await update_hud(page, "04 / 06", "One Folder = One Skill 技能仓 (1,1)", "热插拔高阶管理，集成高性能透明终端与备忘录叠加层")
        await page.wait_for_timeout(4000) # Give 4s to read

        print("Transitioning to Skills & Files view...")
        await page.evaluate("matrix.moveTo(1, 1)")
        await page.wait_for_timeout(2500) # Wait for transition

        # Open Overlay Terminal in Skills view
        print("Opening overlay terminal...")
        await page.evaluate("toggleTerminal()")
        await page.wait_for_timeout(2000)
        # Write simulated commands to xterm.js terminal instance
        await page.evaluate("if (window.term) { window.term.write('butler --version\\r\\n\\u001b[32mBUTLER v2.0.0 [Local-First Architecture]\\u001b[0m\\r\\n\\r\\n$ ') }")
        await page.wait_for_timeout(2500) # Keep terminal open long enough to read
        # Close terminal
        await page.evaluate("toggleTerminal()")
        await page.wait_for_timeout(1500)

        # Open Memo transparent overlays
        print("Opening Memo overlays...")
        await page.evaluate("toggleMemos()")
        await page.wait_for_timeout(2500) # Keep memos open long enough to read
        # Close Memo overlays
        await page.evaluate("toggleMemos()")
        await page.wait_for_timeout(1500)

        # Stage 5: Copilot
        await update_hud(page, "05 / 06", "安全准入：AI Copilot 准入机制", "针对高风险特权指令实施严格确认，支持 Esc 取消与 Tab 焦点捕获")
        await page.wait_for_timeout(4000) # Give 4s to read

        print("Triggering Copilot security dialog...")
        await page.evaluate("matrix.moveTo(0, 0)")  # Move back to Chat quadrant first
        await page.wait_for_timeout(2500)  # Wait for matrix transition to stabilize completely
        await page.evaluate("document.querySelector('.fa-shield-check').click()")
        await page.wait_for_timeout(2500)  # Modal scale-up and backdrop blur animation

        # Click Allow in modal
        print("Approving copilot task...")
        await page.evaluate("document.querySelector('.modal-btn-allow').click()")
        await page.wait_for_timeout(4500)  # Toast triggers and simulated refactoring completes

        # ==========================================
        # PART 2: Local-First Storage Hub UI
        # ==========================================
        print(f"Loading Storage Hub Interface: {storage_hub_url}")
        await page.goto(storage_hub_url)
        await page.wait_for_timeout(1500)
        await init_hud(page)
        await page.wait_for_timeout(1000)

        # Stage 6: Storage Hub
        await update_hud(page, "06 / 06", "Storage Hub 本地网盘聚合仓", "内置 WebDAV 驱动、智能空闲路由，以及高性能零磁盘 IO 跨盘流传输")
        await page.wait_for_timeout(4000) # Give 4s to read

        # Dismiss onboarding spotlight
        print("Dismissing Storage Hub onboarding...")
        await page.evaluate("document.querySelector('.btn-onboard-next').click()")
        await page.wait_for_timeout(1500)

        # Open config modal
        print("Opening Storage Hub config...")
        await page.evaluate("document.getElementById('config-gear-btn').click()")
        await page.wait_for_timeout(2000)

        # Save config & load drives workspace
        print("Saving drives workspace...")
        await page.evaluate("document.querySelector('#drive-config-form button[type=\"submit\"]').click()")
        await page.wait_for_timeout(2500)

        # Hover quota ring details
        print("Showing quota ring details tooltip...")
        await page.hover("#quota-ring-container")
        await page.wait_for_timeout(2000)

        # Open WebDAV card explorer
        print("Opening WebDAV file explorer...")
        await page.evaluate("document.querySelectorAll('.drive-card')[0].click()") # Click the first drive card
        await page.wait_for_timeout(2500)

        # Trigger Context actions
        print("Opening file actions menu...")
        await page.evaluate("document.querySelector('.btn-icon-more').click()")
        await page.wait_for_timeout(2000)

        # Trigger Cross-Drive Transfer popup
        print("Triggering cross-drive target chooser...")
        await page.evaluate("ui.showTargetChooser({ name: 'Ubuntu_24.04_LTS.iso', sourceDrive: 'alist_webdav' })")
        await page.wait_for_timeout(2500)

        # Initiate Transfer
        print("Initiating Microsoft OneDrive transfer...")
        await page.evaluate("document.querySelector('.target-drv-btn').click()") # Click OneDrive option
        await page.wait_for_timeout(6000)  # Wait for progress bar to increment and hit completed state

        # Final pause
        await page.wait_for_timeout(2000)

        # Close browser context to finalize the video
        await context.close()
        await browser.close()
        print("Playwright recording completed successfully!")

if __name__ == "__main__":
    asyncio.run(generate_video())
