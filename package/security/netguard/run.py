"""启动入口"""

import os
import sys

import uvicorn

# 确保 app 目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "true").lower() == "true",
        workers=int(os.getenv("WORKERS", 1)),
    )
