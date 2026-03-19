# Butler-Runner Pro

Butler-Runner Pro 是 Butler 系统的一个轻量级 Go 语言执行节点。它允许 Butler 主系统通过 WebSocket 远程控制其他计算机，执行命令、模拟交互、获取屏幕截图等。

## 核心特性

- **长连接通信**: 基于 WebSocket 的实时指令下发与响应。
- **身份验证**: 强制使用 Token 进行安全校验。
- **应用控制**: 远程启动、关闭和切换应用窗口。
- **模拟交互**: 模拟键盘按键、鼠标点击和文本输入（集成 `robotgo`）。
- **视觉反馈**: 捕获远程屏幕截图并传回。
- **文件操作**: 浏览目录和远程下载文件。
- **系统监控**: 获取操作系统、架构、CPU 核心数等基础信息。
- **智能睡眠**: 支持进入睡眠模式以节省资源，收到指令自动唤醒。

## 安全性指南 (Security Guide)

**安全第一：**

1. **令牌管理 (Token Management)**:
   - 严禁在代码或脚本中公开真实的 Token。
   - Token 建议至少 16 位字符以上，并定期轮换。
   - 默认情况下，Server 拒绝任何无 Token 或使用弱 Token 的连接。

2. **网络隔离 (Network Isolation)**:
   - 服务端默认仅监听 `127.0.0.1:8000`。
   - 如果需要跨机器控制，建议使用 SSH 隧道 (SSH Tunneling) 或 VPN。
   - 严禁在未加密的公网上直接开放 0.0.0.0。

3. **传输加密 (TLS/WSS)**:
   - 建议在服务端前端配置反向代理（如 Nginx 或 Caddy）来终止 TLS。
   - 此时 `runner` 的 `-server` 参数应使用 `wss://` 协议。

## 快速开始

### 1. 编译环境准备

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y libx11-dev libxtst-dev libxext-dev libxinerama-dev libxkbcommon-dev
```

**Windows:**
需要安装 [Mingw-w64](http://mingw-w64.org/)。

### 2. 编译

在 `programs/butler_runner` 目录下运行：
```bash
go mod tidy
go build -o runner runner.go
```

### 3. 运行

```bash
./runner -server ws://localhost:8000/ws/butler -token YOUR_STRONG_TOKEN -id office_pc
```

**参数说明:**
- `-server`: Butler 主控端的 WebSocket 地址。
- `-token`: **(强制)** 身份验证令牌，需与服务端 `system_config.json` 中的 `runner_server.token` 一致。
- `-id`: 该运行节点的唯一标识符。

## 便携模式 (USB 自动开启)

将编译好的 `runner` 放入 U 盘。插入目标电脑后，配置并运行 `run_runner.bat` (Windows) 或 `run_runner.sh` (Unix)。脚本会自动在后台开启并连接到预设的主控端。

---
*Developed by Jules for Butler System.*
