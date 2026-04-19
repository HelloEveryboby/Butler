from playwright.sync_api import sync_playwright
import os
import time

def run_verification():
    screenshot_dir = "assets/ui_screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    with sync_playwright() as p:
        current_dir = os.getcwd()
        file_path = f"file://{current_dir}/frontend/view/index.html"

        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})

        print(f"Opening {file_path}")
        page.goto(file_path)

        # Wait for some initial animations or JS to run
        time.sleep(2)

        # 1. Media View (New)
        print("Switching to Media View...")
        page.click("#nav-media")
        time.sleep(2)
        # Mocking some items if library is empty
        page.evaluate("""() => {
            const list = document.getElementById('media-list');
            list.innerHTML = `
                <div class="media-item-row"><i class="fas fa-music"></i> <span>Sample Music.mp3</span></div>
                <div class="media-item-row"><i class="fas fa-music"></i> <span>Audio Track.wav</span></div>
                <div class="media-item-row"><i class="fas fa-image"></i> <span>Landscape.jpg</span></div>
            `;
            // Trigger selection of first item to show player
            const audioCard = document.getElementById('audio-player-card');
            const titleDisp = document.getElementById('media-title-display');
            const formatInfo = document.getElementById('format-info-content');
            audioCard.classList.remove('hidden');
            titleDisp.innerText = "Sample Music.mp3";
            formatInfo.innerHTML = "<b>MP3 (MPEG-1 Audio Layer III)</b><br>由来：由德国 Fraunhofer 集成电路研究所开发。它是一种有损压缩音频格式，由于其极高的压缩比（约 1:10）和保持良好的音质，在 90 年代互联网早期迅速流行，彻底改变了音乐发行和存储方式。";
        }""")
        page.screenshot(path=f"{screenshot_dir}/ui_media_audio.png")
        print("Captured ui_media_audio.png")

        # 2. Media View - Image
        page.click("#media-filter-image")
        page.evaluate("""() => {
             const audioCard = document.getElementById('audio-player-card');
             const imageCard = document.getElementById('image-viewer-card');
             const formatInfo = document.getElementById('format-info-content');
             audioCard.classList.add('hidden');
             imageCard.classList.remove('hidden');
             formatInfo.innerHTML = "<b>JPG / JPEG (Joint Photographic Experts Group)</b><br>由来：由联合图像专家小组于 1992 年发布。它是针对彩色照片进行的有损压缩标准，利用了人类视觉对色彩变化敏感度低于亮度变化的特性。";
        }""")
        time.sleep(1)
        page.screenshot(path=f"{screenshot_dir}/ui_media_image.png")
        print("Captured ui_media_image.png")

        browser.close()

if __name__ == "__main__":
    run_verification()
