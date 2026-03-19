# Butler-Runner Pro

Butler-Runner Pro 是 Butler 系统的一个轻量级 Go 语言执行节点。它允许 Butler 主系统通过 WebSocket 远程控制其他计算机，执行命令、模拟交互、获取屏幕截图等。

## 核心特性

- **长连接通信**: 基于 WebSocket 的实时指令下发与响应。
- **身份验证**: 使用 Token 进行安全校验。
- **应用控制**: 远程启动、关闭和切换应用窗口。
- **模拟交互**: 模拟键盘按键、鼠标点击和文本输入（集成 `robotgo`）。
- **视觉反馈**: 捕获远程屏幕截图并传回。
- **文件操作**: 浏览目录和远程下载文件。
- **系统监控**: 获取操作系统、架构、CPU 核心数等基础信息。
- **智能睡眠**: 支持进入睡眠模式以节省资源，收到指令自动唤醒。

## 快速开始

### 1. 编译环境准备

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y libx11-dev libxtst-dev libxext-dev libxinerama-dev libxkbcommon-dev
```

**Windows:**
需要安装 [Mingw-w64](http://mingw-w64.org/) 以支持 `robotgo` 的 CGO 编译。

**macOS:**
无需特殊系统依赖，但需授予终端“辅助功能”权限。

### 2. 编译

在 `programs/butler_runner` 目录下运行：
```bash
go mod tidy
go build -o runner runner.go
```

### 3. 运行

```bash
./runner -server ws://YOUR_SERVER_IP:8000/ws/butler -token YOUR_SECRET_TOKEN -id office_pc
```

**参数说明:**
- `-server`: Butler 主控端的 WebSocket 地址。
- `-token`: 身份验证令牌，需与服务端配置一致。
- `-id`: 该运行节点的唯一标识符（如 `living_room`, `macbook_pro`）。

## 通信协议 (BHL over WebSocket)

### 指令格式 (Message)
```json
{
  "type": "screenshot",
  "payload": "",
  "token": "BUTLER_SECRET_2026",
  "runner_id": "optional_id"
}
```

### 响应格式 (Response)
```json
{
  "status": "screenshot",
  "data": "BASE64_ENCODED_IMAGE_DATA",
  "runner_id": "office_pc"
}
```

## 便携模式 (USB 自动开启)

你可以将编译好的 `runner` 二进制文件放入 U 盘。在目标电脑上插入 U 盘后，运行预设的启动脚本（如 `run_runner.bat`），它将自动在后台开启并连接到预设的主控端。

---
*Developed by Jules for Butler System.*
