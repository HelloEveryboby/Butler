import os
import sys
import logging
import webbrowser
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DocumentStudio")

# Add project root to path for correct importing
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from flask import Flask, request, jsonify, render_template_string
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


def check_and_install_dependencies():
    """Checks and reports missing optional document conversion packages."""
    missing = []
    try:
        import docx
    except ImportError:
        missing.append("python-docx")
    try:
        import PIL
    except ImportError:
        missing.append("pillow")
    try:
        import reportlab
    except ImportError:
        missing.append("reportlab")

    if missing:
        logger.info("=" * 60)
        logger.info("💡 提示: 检测到以下可选转换库尚未安装。若需完整功能，建议安装:")
        logger.info(f"   pip install {' '.join(missing)}")
        logger.info("=" * 60)
    else:
        logger.info("✅ 所有的文档格式转换底层核心依赖检测已全部通过！")


def create_app():
    if not FLASK_AVAILABLE:
        # Emergency simple server using http.server if Flask is missing
        logger.warning("Flask is not installed in the environment. Standalone mode cannot run Flask webserver.")
        return None

    app = Flask(__name__)

    # Load the gorgeous template content
    template_path = Path(__file__).resolve().parent / "templates" / "export_ui.html"
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    else:
        template_content = "<h1>Butler Document Studio Template Not Found</h1>"

    @app.route("/")
    def index():
        return render_template_string(template_content)

    @app.route("/api/convert", methods=["POST"])
    def convert_api():
        from skills.format_convert.format_convert import handle_request
        try:
            data = request.json or {}
            input_val = data.get("input")
            from_fmt = data.get("from", "MD")
            to_fmt = data.get("to")
            options = data.get("options", {})

            if not input_val or not to_fmt:
                return jsonify({"status": "error", "error": "Missing parameters 'input' or 'to'"}), 400

            # Execute format conversion using handle_request with unpacked keyword arguments
            # to avoid Python keyword collision on "from"
            kwargs = {
                "input": input_val,
                "from": from_fmt,
                "to": to_fmt,
                "options": options
            }
            res = handle_request(action="run", **kwargs)

            if isinstance(res, str) and res.startswith("Error:"):
                return jsonify({"status": "error", "error": res})

            return jsonify({
                "status": "ok",
                "base64": res
            })

        except Exception as e:
            logger.error(f"API conversion failed: {e}", exc_info=True)
            return jsonify({"status": "error", "error": str(e)}), 500

    return app


def main():
    check_and_install_dependencies()

    app = create_app()
    if not app:
        logger.error("无法启动本地 Web 服务：缺少 Flask。请通过 pip install flask 安装。")
        sys.exit(1)

    port = 8011
    url = f"http://127.0.0.1:{port}"
    logger.info(f"🚀 Butler Document Studio (极简文档工作室) 正在启动...")
    logger.info(f"🔗 本地 Web 预览页面地址: {url}")

    # Auto open browser
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.warning(f"无法自动打开浏览器: {e}")

    # Run Flask app (host on 127.0.0.1 for local isolation and security)
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
