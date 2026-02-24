import asyncio
from playwright.async_api import async_playwright
import os

async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1200, 'height': 800})

        path = os.path.abspath('butler/web/index.html')
        await page.goto(f'file://{path}')

        await asyncio.sleep(2)

        await page.evaluate("""() => {
            const flow = document.getElementById('interaction-flow');

            // Clear welcome message to show interaction better
            document.querySelector('.welcome-message').style.display = 'none';

            const userLine = document.createElement('div');
            userLine.className = 'interaction-line user-input-line';
            userLine.innerHTML = '<span>帮我分析一下最近的系统日志</span>';
            flow.appendChild(userLine);

            const aiLine = document.createElement('div');
            aiLine.className = 'interaction-line ai-output-line';
            aiLine.innerText = '正在为您检索系统日志... 发现 3 条异常记录。已自动为您启动高性能终端进行深度排查。';
            flow.appendChild(aiLine);

            const inputLine = document.createElement('div');
            inputLine.className = 'interaction-line user-input-line';
            const inputSpan = document.createElement('span');
            inputSpan.className = 'active-input';
            inputSpan.contentEditable = true;
            inputLine.appendChild(inputSpan);
            flow.appendChild(inputLine);
        }""")

        await asyncio.sleep(1)
        os.makedirs('assets', exist_ok=True)
        await page.screenshot(path='assets/UI_Preview.png', full_page=True)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(capture())
