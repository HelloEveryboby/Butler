# syntax=docker/dockerfile:1
# Butler 容器化部署 —— 多阶段构建
#
# 相比旧版单阶段镜像，本文件带来的改进：
#   1. 多阶段构建：编译期依赖（gcc/python3-dev 等）不进入最终镜像，体积更小。
#   2. 非 root 运行：以普通用户 `butler` 运行，降低容器逃逸面。
#   3. 平台中立：基于 python:3.12-slim，linux/amd64 与 linux/arm64 均可构建
#      （配合 `docker buildx build --platform linux/amd64,linux/arm64` 即可出多架构产物）。
#   4. 健康检查：内置 HEALTHCHECK 模板（按实际健康端点启用）。

# ---------- 构建阶段 ----------
FROM python:3.12-slim AS builder

WORKDIR /app

# 编译 OpenCV / 部分原生扩展所需工具链，仅存在于本阶段
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ python3-dev \
        libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md requirements.txt ./
# 预构建 wheel，充分利用 Docker layer cache（依赖不变则跳过重装）
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt \
    && pip wheel --no-cache-dir --wheel-dir /wheels .

# ---------- 运行阶段 ----------
FROM python:3.12-slim

WORKDIR /app

# 运行期最小系统依赖 + 非 root 用户
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r butler && useradd -r -g butler butler

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

COPY . .
RUN chown -R butler:butler /app
USER butler

# REST API / Modern UI
EXPOSE 5001 8000 3000

ENV PYTHONUNBUFFERED=1 \
    BUTLER_MODE=container

# 健康检查：请把 URL 改成 Butler 实际暴露的健康端点后取消注释启用
# HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
#   CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5001/health', timeout=3)"

CMD ["python", "-m", "butler.butler_app", "--headless"]
