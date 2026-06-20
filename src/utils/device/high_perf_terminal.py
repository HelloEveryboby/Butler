import os
import sys
import webview
import json
import threading

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from butler.core.hybrid_link import HybridLinkClient

class TerminalBridge:
    def __init__(self, window):
        self.window = window
        self.terminal_client = None

    def start_terminal(self):
        terminal_path = os.path.join(project_root, "programs/hybrid_terminal/terminal_service")
        self.terminal_client = HybridLinkClient(
            executable_path=terminal_path,
            fallback_enabled=False
        )
        self.terminal_client.start()

        def on_event(event):
            if event.get("method") == "terminal_output":
                output = event.get("params")
                self.window.evaluate_js(f"window.onTerminalOutput({json.dumps(output)})")

        self.terminal_client.register_event_callback(on_event)
        self.terminal_client.call("start_terminal", {})

    def terminal_input(self, data):
        if self.terminal_client:
            self.terminal_client.call("write_input", {"data": data})

def run():
    # This HTML is a minimal version of the terminal part
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.1.0/css/xterm.min.css">
        <script src="https://cdn.jsdelivr.net/npm/xterm@5.1.0/lib/xterm.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.7.0/lib/xterm-addon-fit.min.js"></script>
        <style>
            body { margin: 0; background: #1e1e1e; height: 100vh; overflow: hidden; }
            #terminal { height: 100vh; }
        </style>
    </head>
    <body>
        <div id="terminal"></div>
        <script>
            const term = new Terminal({
                cursorBlink: true,
                theme: { background: '#1e1e1e' },
                fontSize: 14
            });
            const fitAddon = new FitAddon.FitAddon();
            term.loadAddon(fitAddon);
            term.open(document.getElementById('terminal'));

            function fitTerminal() {
                fitAddon.fit();
            }

            window.addEventListener('resize', fitTerminal);
            setTimeout(fitTerminal, 100);

            term.onData(data => {
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.terminal_input(data);
                }
            });

            window.onTerminalOutput = (data) => { term.write(data); };

            window.onload = () => {
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.start_terminal();
                }
            };
        </script>
    </body>
    </html>
    """

    window = webview.create_window('Butler Independent Terminal', html=html, width=800, height=600)
    bridge = TerminalBridge(window)
    window.expose(bridge)
    webview.start()

if __name__ == "__main__":
    run()
