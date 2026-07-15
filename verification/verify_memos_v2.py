import os
import sys
from playwright.sync_api import sync_playwright

def run_cuj(page):
    # Enable console log forwarding
    page.on("console", lambda msg: print(f"PAGE CONSOLE: {msg.text}"))
    page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))

    # 1. Inject a robust pywebview mock layer
    page.add_init_script("""
        window.pywebview = {
            api: {
                call_skill: function(skill_id, action, params) {
                    console.log("[MOCK pywebview.api.call_skill]", skill_id, action, params);
                    if (skill_id === "memos" && action === "list") {
                        return [
                            {
                                id: 1,
                                content: "### 💡 Butler V2 核心记忆池设计\\n我们基于 SQLite 和 Zvec 向量数据库构建了双层降级缓存，使得毫秒级的记忆检索成为可能。 #技术 #架构",
                                tags: ["#技术", "#架构"],
                                resources: ["data/memos/attachments/architecture.png"],
                                created_at: Math.floor(Date.now() / 1000) - 3600 * 2,
                                updated_at: Math.floor(Date.now() / 1000) - 3600 * 2,
                                is_pinned: 1,
                                is_archived: 0
                            },
                            {
                                id: 2,
                                content: "今天的天气真好，非常适合出去散步和写代码。顺便记录一下关于局域网代码同步的优化思路。 #日常 #灵感",
                                tags: ["#日常", "#灵感"],
                                resources: [],
                                created_at: Math.floor(Date.now() / 1000) - 3600 * 5,
                                updated_at: Math.floor(Date.now() / 1000) - 3600 * 5,
                                is_pinned: 0,
                                is_archived: 0
                            },
                            {
                                id: 3,
                                content: "🎙️ 离线 FFT 降噪会议记录音频。听起来底噪已经降到了 -45dB 以下，效果非常明显。 #技术 #会议",
                                tags: ["#技术", "#会议"],
                                resources: ["data/memos/attachments/meeting_audio.mp3"],
                                created_at: Math.floor(Date.now() / 1000) - 3600 * 24 * 2,
                                updated_at: Math.floor(Date.now() / 1000) - 3600 * 24 * 2,
                                is_pinned: 0,
                                is_archived: 0
                            }
                        ];
                    }
                    if (skill_id === "memos" && action === "ai_tag_predict") {
                        return ["#技术", "#灵感", "#会议"];
                    }
                    if (skill_id === "memos" && action === "ai_magic_wand") {
                        if (params && params.mode === "summary") {
                            return "### 💡 Butler V2 核心记忆池摘要\\n采用 SQLite + Zvec 缓存架构，实现毫秒级快速记忆检索。";
                        }
                        return "### MOCK AI Magic Wand Output";
                    }
                    return "success";
                },
                get_ui_skills: function() {
                    return [
                        {
                            id: "memos",
                            name: "备忘录",
                            icon: "fa-sticky-note",
                            frontend_path: "frontend/index.html"
                        }
                    ];
                },
                list_files: function(path) {
                    return [];
                }
            }
        };
    """)

    # 2. Go to the page
    html_path = os.path.abspath("frontend/index.html")
    page.goto(f"file://{html_path}")
    page.wait_for_timeout(1000)

    # 3. Dismiss onboarding and setup UI
    page.evaluate("window.skipOnboarding()")
    page.wait_for_timeout(500)

    # 4. Open Memos Overlay
    page.evaluate("window.toggleMemos()")
    page.wait_for_timeout(1000)

    # Print state of memos overlay and editor container
    overlay_hidden = page.evaluate("document.getElementById('memos-overlay').classList.contains('hidden')")
    editor_hidden = page.evaluate("document.getElementById('memo-editor-container').classList.contains('hidden')")
    print(f"DEBUG BEFORE CLICK: overlay_hidden={overlay_hidden}, editor_hidden={editor_hidden}")

    # 5. Open New Memo Editor
    page.click("#new-memo-btn")
    page.wait_for_timeout(1000)

    # Print state of editor container after click
    editor_hidden_after = page.evaluate("document.getElementById('memo-editor-container').classList.contains('hidden')")
    editor_style_display = page.evaluate("document.getElementById('memo-editor-container').style.display")
    print(f"DEBUG AFTER CLICK: editor_hidden_after={editor_hidden_after}, editor_style_display={editor_style_display}")

    # 6. Fill in text with markdown and tag
    # Use force parameter or set content directly if needed
    page.evaluate("document.getElementById('memo-content-input').value = '### ⚡ 智能助理自愈引擎\\n当 Butler 核心逻辑在沙箱执行发生异常时，自愈系统会自动捕获并启动 LLM 修复方案，确保运行不中断。 #技术 #AI'")
    page.wait_for_timeout(800)

    # 7. Click on view modes (Gallery and Spatial)
    page.click("#memos-gallery-view-btn")
    page.wait_for_timeout(1000)

    # 8. Trigger AI Magic Wand summaries
    page.click("#memo-ai-magic-btn")
    page.wait_for_timeout(500)
    page.click(".ai-menu-item[data-action='summary']")
    page.wait_for_timeout(1500)

    # 9. Take final screenshot
    page.screenshot(path="/home/jules/verification/screenshots/verification.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="/home/jules/verification/videos",
            viewport={"width": 1200, "height": 800}
        )
        page = context.new_page()
        try:
            run_cuj(page)
        finally:
            context.close()
            browser.close()
    print("Verification execution complete successfully.")
