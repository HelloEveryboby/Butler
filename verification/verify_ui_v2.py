from playwright.sync_api import sync_playwright
import os
import time

def run_verification():
    ui_2_0_dir = "assets/ui_2_0"
    ui_screenshots_dir = "assets/ui_screenshots"
    os.makedirs(ui_2_0_dir, exist_ok=True)
    os.makedirs(ui_screenshots_dir, exist_ok=True)

    with sync_playwright() as p:
        current_dir = os.getcwd()
        file_path = f"file://{current_dir}/frontend/index.html"

        # Launch chromium with nice standard resolution
        browser = p.chromium.launch(headless=True)
        # Use a high quality Apple-standard display aspect ratio/viewport
        page = browser.new_page(viewport={'width': 1280, 'height': 800})

        print(f"Opening {file_path}")
        page.goto(file_path)

        # Wait for fonts, icons, and monaco/xterm CDN resources to load
        time.sleep(3)

        # ----------------------------------------------------
        # 1. Capture Smart Chat View (0, 0)
        # ----------------------------------------------------
        print("Preparing Smart Chat (0,0) quadrant...")
        page.evaluate("""() => {
            // Focus on Quadrant 0,0
            window.stateMatrix.update('matrix.x', 0);
            window.stateMatrix.update('matrix.y', 0);
            window.stateMatrix.update('matrix.targetX', 0);
            window.stateMatrix.update('matrix.targetY', 0);

            // Hide the welcome message
            const welcome = document.querySelector('.welcome-message');
            if (welcome) welcome.style.display = 'none';

            // Inject gorgeous mock communication
            const flow = document.getElementById('interaction-flow');
            flow.innerHTML = `
                <div class="interaction-line user-input-line" style="margin-bottom: 12px; animation: none;">分析系统负载，开启自愈重构并检查冲突。</div>
                <div class="interaction-line ai-output-line" style="margin-bottom: 12px; animation: none;">
                    <strong>Jarvis:</strong> 收到指令。正在进行局域网与系统环境深度扫描...<br>
                    扫描发现：<br>
                    • SQLite FTS5 向量检索库: <span style="color: #34C759;">ACTIVE</span> (本地秒级降级机制已就绪)<br>
                    • C++ Audio FFT 音频引擎: <span style="color: #34C759;">ONLINE</span> (0.2ms 超低延迟)<br>
                    • gRPC 发现集群节点: <span style="color: #007AFF;">192.168.1.104 (AgentNode_B)</span>
                </div>
                <div class="fix-card glass-surface" style="margin-bottom: 12px; animation: none; background: rgba(52, 199, 89, 0.15); border: 1px solid rgba(52, 199, 89, 0.4);">
                    <div style="font-weight: 700; color: #34C759; display: flex; align-items: center; gap: 8px; font-size: 16px;">
                        <i class="fas fa-magic"></i> 检测到底层模块冲突 (butler/core/workflow_engine.py)
                    </div>
                    <p style="font-size: 14px; opacity: 0.95; line-height: 1.5; color: #f5f5f7;">
                        在第 142 行检测到任务 DAG 节点的循环引用风险，系统已被拦截。<br>
                        <strong>建议：</strong> 一键执行 KAIROS 时间缝隙（Time-Slit）自动修复逻辑。
                    </p>
                    <button class="fix-btn apple-btn-primary" style="align-self: flex-start; background: #34C759; border-radius: 8px; padding: 6px 16px;">
                        一键修复逻辑 (Time-Slit)
                    </button>
                </div>
            `;
        }""")
        time.sleep(1)
        # Capture and save to both folders
        page.screenshot(path=f"{ui_2_0_dir}/matrix_chat.png")
        page.screenshot(path=f"{ui_screenshots_dir}/ui_chat.png")
        print("Captured and saved Smart Chat view.")

        # ----------------------------------------------------
        # 2. Capture Time Machine View (1, 0)
        # ----------------------------------------------------
        print("Preparing Time Machine (1,0) quadrant...")
        page.evaluate("""() => {
            // Focus on Quadrant 1,0
            window.stateMatrix.update('matrix.x', 1);
            window.stateMatrix.update('matrix.y', 0);
            window.stateMatrix.update('matrix.targetX', 1);
            window.stateMatrix.update('matrix.targetY', 0);

            // Populating metrics visualizer
            const metrics = document.getElementById('tm-metrics');
            metrics.innerHTML = `
                <div style="padding: 20px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; height: 100%; box-sizing: border-box; align-content: center;">
                    <div class="glass-surface" style="padding: 16px; border-radius: 12px; text-align: center; border: 1px solid rgba(52, 199, 89, 0.2); background: rgba(255,255,255,0.03);">
                        <div style="font-size: 12px; color: var(--text-secondary); text-transform: uppercase;">CPU 负载</div>
                        <div style="font-size: 26px; font-weight: bold; color: #30d158; margin-top: 8px; font-family: SFMono-Regular, monospace;">24.5 %</div>
                    </div>
                    <div class="glass-surface" style="padding: 16px; border-radius: 12px; text-align: center; border: 1px solid rgba(0, 122, 255, 0.2); background: rgba(255,255,255,0.03);">
                        <div style="font-size: 12px; color: var(--text-secondary); text-transform: uppercase;">内存物理占用</div>
                        <div style="font-size: 26px; font-weight: bold; color: #0a84ff; margin-top: 8px; font-family: SFMono-Regular, monospace;">4.21 GB</div>
                    </div>
                    <div class="glass-surface" style="padding: 16px; border-radius: 12px; text-align: center; border: 1px solid rgba(191, 90, 242, 0.2); background: rgba(255,255,255,0.03);">
                        <div style="font-size: 12px; color: var(--text-secondary); text-transform: uppercase;">磁盘 IO 速度</div>
                        <div style="font-size: 26px; font-weight: bold; color: #bf5af2; margin-top: 8px; font-family: SFMono-Regular, monospace;">12.8 MB/s</div>
                    </div>
                    <div class="glass-surface" style="padding: 16px; border-radius: 12px; text-align: center; border: 1px solid rgba(255, 159, 10, 0.2); background: rgba(255,255,255,0.03);">
                        <div style="font-size: 12px; color: var(--text-secondary); text-transform: uppercase;">活跃协程/线程</div>
                        <div style="font-size: 26px; font-weight: bold; color: #ff9f0a; margin-top: 8px; font-family: SFMono-Regular, monospace;">42 goroutines</div>
                    </div>
                </div>
            `;

            // Populating real logs
            const logs = document.getElementById('tm-logs');
            logs.style.fontSize = "13px";
            logs.style.lineHeight = "1.6";
            logs.innerHTML = `
                <div style="color: #30d158; margin-bottom: 6px;"><span style="color: #8e8e93;">[10:00:12]</span> [INFO] KAIROS 自动化自愈配置初始化完毕。</div>
                <div style="color: #30d158; margin-bottom: 6px;"><span style="color: #8e8e93;">[10:00:15]</span> [INFO] SecretVault 解密机制开启，AES-256-GCM 验证通过。</div>
                <div style="color: #ff9f0a; margin-bottom: 6px;"><span style="color: #8e8e93;">[10:00:18]</span> [WARN] 未连接到物理 STM32 网关核心，自动激活全软件平滑降级模式。</div>
                <div style="color: #bf5af2; margin-bottom: 6px;"><span style="color: #8e8e93;">[10:00:22]</span> [DEBUG] 远程 Redis 向量数据库不可达。Zvec 嵌入式向量层自动启动，本地 FTS5 索引重组中。</div>
                <div style="color: #30d158; margin-bottom: 6px;"><span style="color: #8e8e93;">[10:00:25]</span> [SUCCESS] 模块安全自检完成，Butler 已处于极致安全的 Local-First 本地闭环。</div>
            `;
        }""")
        time.sleep(1)
        # Capture and save to both folders
        page.screenshot(path=f"{ui_2_0_dir}/matrix_timemachine.png")
        page.screenshot(path=f"{ui_screenshots_dir}/ui_timemachine.png")
        print("Captured and saved Time Machine view.")

        # ----------------------------------------------------
        # 3. Capture DAG Pipeline View (0, 1)
        # ----------------------------------------------------
        print("Preparing DAG Pipeline (0,1) quadrant...")
        page.evaluate("""() => {
            // Focus on Quadrant 0,1
            window.stateMatrix.update('matrix.x', 0);
            window.stateMatrix.update('matrix.y', 1);
            window.stateMatrix.update('matrix.targetX', 0);
            window.stateMatrix.update('matrix.targetY', 1);

            // Hide placeholder
            const placeholder = document.querySelector('.canvas-placeholder');
            if (placeholder) placeholder.style.display = 'none';
        }""")
        time.sleep(0.5)

        # Add nodes with small delays to avoid Date.now() timestamp collisions
        page.evaluate("window.dagEngine.addNode('截图排障', 'fa-bug', 150, 200)")
        time.sleep(0.1)
        page.evaluate("window.dagEngine.addNode('系统自愈', 'fa-magic', 400, 200)")
        time.sleep(0.1)
        page.evaluate("window.dagEngine.addNode('存储中心', 'fa-box-open', 650, 200)")
        time.sleep(0.5)

        # Create connections between nodes
        page.evaluate("""() => {
            const nodes = window.dagEngine.nodes;
            if (nodes.length >= 3) {
                window.dagEngine.connections.push({
                    from: nodes[0].id,
                    to: nodes[1].id
                });
                window.dagEngine.connections.push({
                    from: nodes[1].id,
                    to: nodes[2].id
                });
            }
        }""")
        time.sleep(1)
        # Capture and save to both folders
        page.screenshot(path=f"{ui_2_0_dir}/matrix_dag.png")
        page.screenshot(path=f"{ui_screenshots_dir}/ui_workspace.png") # Match old verify file name
        print("Captured and saved DAG Pipeline view.")

        # ----------------------------------------------------
        # 4. Capture Skills & Terminal View (1, 1)
        # ----------------------------------------------------
        print("Preparing Skills & Terminal (1,1) quadrant...")
        page.evaluate("""() => {
            // Focus on Quadrant 1,1
            window.stateMatrix.update('matrix.x', 1);
            window.stateMatrix.update('matrix.y', 1);
            window.stateMatrix.update('matrix.targetX', 1);
            window.stateMatrix.update('matrix.targetY', 1);

            // Open Terminal Overlay
            if (document.getElementById('terminal-overlay').classList.contains('hidden')) {
                window.toggleTerminal();
            }
        }""")
        time.sleep(1)

        # Write beautiful logs to the Xterm.js terminal instance
        page.evaluate("""() => {
            if (window.term) {
                window.term.write('\\x1b[36mbutler status\\x1b[0m\\r\\n');
                window.term.write('[System] Jarvis Matrix UI 3.0 CLI Client v2.0.0\\r\\n');
                window.term.write('[System] Synchronizing environment variable mapping with local storage...\\r\\n\\r\\n');
                window.term.write('\\x1b[32m✔ KAIROS Core Orchestrator status: ACTIVE\\x1b[0m\\r\\n');
                window.term.write('\\x1b[32m✔ High-Performance Binary Hybrid Link (BHL): ENABLED\\x1b[0m\\r\\n');
                window.term.write('\\x1b[32m✔ Dream Engine background cron processor: ONLINE (Midnight Dreaming)\\x1b[0m\\r\\n');
                window.term.write('\\x1b[33m⚡ HAL Hardware sensors gateway: SOFT_FALLBACK (No physical STM32 found)\\x1b[0m\\r\\n\\r\\n');
                window.term.write('butler > ');
            }
        }""")
        time.sleep(1)
        # Capture and save to both folders
        page.screenshot(path=f"{ui_2_0_dir}/matrix_terminal.png")
        page.screenshot(path=f"{ui_screenshots_dir}/ui_terminal.png")
        print("Captured and saved Skills & Terminal view.")

        # Let's generate a general view as well for completeness if needed (like workspace view, ui_files etc.)
        # Hide terminal and take quadrant (1, 1) view showing skills drawer & files mini-list
        print("Preparing Files & Skills Grid view...")
        page.evaluate("""() => {
            if (!document.getElementById('terminal-overlay').classList.contains('hidden')) {
                window.toggleTerminal();
            }
        }""")
        time.sleep(1)
        page.screenshot(path=f"{ui_screenshots_dir}/ui_files.png")
        print("Captured and saved Files & Skills view.")

        browser.close()

if __name__ == "__main__":
    run_verification()
