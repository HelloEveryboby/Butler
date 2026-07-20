import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

def generate_screenshots():
    project_root = Path(__file__).resolve().parent.parent
    html_path = project_root / "skills/pixel_pet/ui/index.html"
    output_path = project_root / "assets/pixel_pet_preview.png"

    # Ensure assets directory exists
    (project_root / "assets").mkdir(parents=True, exist_ok=True)

    print(f"Loading local HTML: {html_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Create a page with a specific dark background to simulate a real desktop placement
        context = browser.new_context(viewport={"width": 600, "height": 400})
        page = context.new_page()

        # Load index.html
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(1000)

        # Let's inject a beautiful dark blurred desktop wallpaper background in body so the transparent pet is clearly visible!
        page.evaluate("""
            document.body.style.background = 'radial-gradient(circle at center, #1e1e2e 0%, #0f0f16 100%)';
            document.body.style.display = 'flex';
            document.body.style.justifyContent = 'center';
            document.body.style.alignItems = 'center';
            document.body.style.height = '100vh';

            // Adjust pet container size for a wider grid layout
            const container = document.getElementById('pet-container');
            container.style.width = '300px';
            container.style.height = '300px';
            container.style.justifyContent = 'center';
        """)

        # Capture state 1: Idle
        print("Capturing state: IDLE")
        page.evaluate('window.ButlerPet.onEvent({"event": "user_idle", "message": "Butler 正在安全守护中"})')
        page.wait_for_timeout(1500)
        page.screenshot(path=str(project_root / "assets/pet_state_idle.png"))

        # Capture state 2: Thinking
        print("Capturing state: THINKING")
        page.evaluate('window.ButlerPet.onEvent({"event": "ai_thinking", "message": "智能助手正在深入思考..."})')
        page.wait_for_timeout(1500)
        page.screenshot(path=str(project_root / "assets/pet_state_thinking.png"))

        # Capture state 3: Generating
        print("Capturing state: GENERATING")
        page.evaluate('window.ButlerPet.onEvent({"event": "ai_streaming", "message": "正在高速流式传输中..."})')
        page.wait_for_timeout(1500)
        page.screenshot(path=str(project_root / "assets/pet_state_generating.png"))

        # Capture state 4: Success
        print("Capturing state: SUCCESS")
        page.evaluate('window.ButlerPet.onEvent({"event": "task_success", "message": "任务成功完成！"})')
        page.wait_for_timeout(1500)
        page.screenshot(path=str(project_root / "assets/pet_state_success.png"))

        # Capture state 5: Error
        print("Capturing state: ERROR")
        page.evaluate('window.ButlerPet.onEvent({"event": "task_failed", "message": "警告: 触发异常错误!"})')
        page.wait_for_timeout(1500)
        page.screenshot(path=str(project_root / "assets/pet_state_error.png"))

        # Let's create a stitched HTML dashboard to present all 5 states in a single gorgeous preview image!
        # This will be compiled into assets/pixel_pet_preview.png
        print("Generating stitched showcase image...")
        showcase_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    margin: 0;
                    padding: 30px;
                    background: radial-gradient(circle at center, #1e1e2e 0%, #0f0f16 100%);
                    font-family: 'SF Pro', -apple-system, sans-serif;
                    color: #fff;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    box-sizing: border-box;
                }
                .title {
                    font-size: 24px;
                    font-weight: 600;
                    margin-bottom: 5px;
                    letter-spacing: 1px;
                }
                .subtitle {
                    font-size: 14px;
                    color: #a6adc8;
                    margin-bottom: 30px;
                }
                .grid {
                    display: flex;
                    gap: 20px;
                    justify-content: center;
                }
                .card {
                    background: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 16px;
                    padding: 15px;
                    width: 140px;
                    height: 240px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: space-between;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                }
                .state-name {
                    font-size: 12px;
                    font-weight: bold;
                    color: #cdd6f4;
                    text-transform: uppercase;
                    background: rgba(255,255,255,0.08);
                    padding: 4px 10px;
                    border-radius: 20px;
                }
                iframe {
                    border: none;
                    width: 120px;
                    height: 180px;
                }
            </style>
        </head>
        <body>
            <div class="title">Butler Pixel Pet Showcase</div>
            <div class="subtitle">Five standard state animations in an Apple-style glassmorphism interface</div>
            <div class="grid">
                <div class="card">
                    <iframe id="f1" src="index.html"></iframe>
                    <div class="state-name">Idle</div>
                </div>
                <div class="card">
                    <iframe id="f2" src="index.html"></iframe>
                    <div class="state-name">Thinking</div>
                </div>
                <div class="card">
                    <iframe id="f3" src="index.html"></iframe>
                    <div class="state-name">Generating</div>
                </div>
                <div class="card">
                    <iframe id="f4" src="index.html"></iframe>
                    <div class="state-name">Success</div>
                </div>
                <div class="card">
                    <iframe id="f5" src="index.html"></iframe>
                    <div class="state-name">Error</div>
                </div>
            </div>

            <script>
                function setFrameState(id, event, message) {
                    const iframe = document.getElementById(id);
                    const run = () => {
                        try {
                            if (iframe.contentWindow && iframe.contentWindow.ButlerPet) {
                                // Wait slightly to make sure the iframe's own initial resetToIdle has finished executing
                                setTimeout(() => {
                                    iframe.contentWindow.ButlerPet.onEvent({"event": event, "message": message});
                                }, 200);
                            } else {
                                setTimeout(run, 50);
                            }
                        } catch (e) {
                            setTimeout(run, 50);
                        }
                    };
                    run();
                }
                window.onload = () => {
                    setFrameState('f1', 'user_idle', '安全守护中');
                    setFrameState('f2', 'ai_thinking', '思考中...');
                    setFrameState('f3', 'ai_streaming', '流式生成中...');
                    setFrameState('f4', 'task_success', '执行成功');
                    setFrameState('f5', 'task_failed', '异常错误: 104');
                }
            </script>
        </body>
        </html>
        """

        # Write temporary showcase HTML next to index.html to load it via relative path
        showcase_path = project_root / "skills/pixel_pet/ui/showcase.html"
        showcase_path.write_text(showcase_html, encoding="utf-8")

        # Capture showcase
        showcase_page = context.new_page()
        showcase_page.set_viewport_size({"width": 900, "height": 500})
        showcase_page.goto(f"file://{showcase_path.resolve()}")
        showcase_page.wait_for_timeout(2000) # Wait for iframe state load
        showcase_page.screenshot(path=str(output_path))
        print(f"Showcase preview saved to: {output_path}")

        # Clean up temporary showcase.html
        if showcase_path.exists():
            showcase_path.unlink()

        browser.close()

if __name__ == "__main__":
    generate_screenshots()
