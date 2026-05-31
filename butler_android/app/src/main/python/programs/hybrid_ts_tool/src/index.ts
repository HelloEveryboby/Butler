import * as readline from 'readline';

/**
 * Butler TypeScript 混合编程示例模块
 * --------------------------------
 * 展示如何通过 BHL 协议集成 TypeScript 逻辑。
 */

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

function sendResult(id: string, result: any) {
    console.log(JSON.stringify({
        jsonrpc: "2.0",
        result: result,
        id: id
    }));
}

function sendError(id: string, code: number, message: string) {
    console.log(JSON.stringify({
        jsonrpc: "2.0",
        error: { code, message },
        id: id
    }));
}

rl.on('line', (line) => {
    try {
        const request = JSON.parse(line);
        const { method, params, id } = request;

        switch (method) {
            case 'hello_ts':
                sendResult(id, { message: "你好！这是来自 TypeScript 的问候。", timestamp: Date.now() });
                break;
            case 'analyze_ts':
                // 模拟一个复杂的分析逻辑
                const codeLength = params.code?.length || 0;
                sendResult(id, { analysis: `代码长度为 ${codeLength}，结构分析完成（模拟）` });
                break;
            case 'exit':
                process.exit(0);
                break;
            default:
                sendError(id, -32601, "未找到该方法");
        }
    } catch (err) {
        // 忽略非 JSON 输入
    }
});

console.error("TypeScript 混合模块已就绪");
