# Butler 容器化部署 Dockerfile
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    python3-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖和配置文件（利用 Docker layer cache）
COPY pyproject.toml setup.py README.md ./

# 安装依赖
RUN pip install --no-cache-dir .

# 复制项目代码
COPY . .

# 暴露端口 (REST API & Modern UI)
EXPOSE 5001 8000 3000

# 环境变量设置
ENV PYTHONUNBUFFERED=1
ENV BUTLER_MODE=container

# 启动命令 (默认启动 Modern UI 模式)
CMD ["python", "-m", "butler.butler_app", "--headless"]
