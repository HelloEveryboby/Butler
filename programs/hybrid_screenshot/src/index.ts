import * as readline from 'readline';

/**
 * Butler Screenshot Hybrid Module (TypeScript)
 * -------------------------------------------
 * Handles high-level screenshot features like Playwright scroll capture.
 */

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

function sendResult(id: string | null, result: any) {
    console.log(JSON.stringify({
        jsonrpc: "2.0",
        result: result,
        id: id
    }));
}

function sendError(id: string | null, code: number, message: string) {
    console.log(JSON.stringify({
        jsonrpc: "2.0",
        error: { code, message },
        id: id
    }));
}

rl.on('line', async (line) => {
    try {
        const request = JSON.parse(line);
        const { method, params, id } = request;

        switch (method) {
            case 'ping':
                sendResult(id, "pong");
                break;
            case 'web_scroll_capture':
                try {
                    const { chromium } = require('playwright');
                    const browser = await chromium.launch({ headless: true });
                    const context = await browser.newContext();
                    const page = await context.newPage();

                    await page.goto(params.url, { waitUntil: 'networkidle', timeout: 30000 });

                    // Support for auto-scrolling to trigger lazy loading
                    await page.evaluate(async () => {
                        await new Promise((resolve) => {
                            let totalHeight = 0;
                            const distance = 100;
                            const timer = setInterval(() => {
                                const scrollHeight = document.body.scrollHeight;
                                window.scrollBy(0, distance);
                                totalHeight += distance;
                                if(totalHeight >= scrollHeight){
                                    clearInterval(timer);
                                    resolve(null);
                                }
                            }, 100);
                        });
                    });

                    await page.screenshot({ path: params.outputPath, fullPage: true });
                    await browser.close();
                    sendResult(id, { status: "success", path: params.outputPath });
                } catch (e: any) {
                    sendError(id, -32000, e.message);
                }
                break;
            case 'exit':
                process.exit(0);
                break;
            default:
                sendError(id, -32601, "Method not found");
        }
    } catch (err) {
        // Ignore invalid JSON
    }
});

console.error("Screenshot TS Module Initialized");
