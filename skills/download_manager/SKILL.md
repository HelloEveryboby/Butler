---
id: download_manager
name: 下载管理器
description: 基于 Aria2 的多线程下载管理器，支持 HTTP/FTP/BT/Magnet
version: 1.0.0
author: Butler
icon: fa-download
risk: low
keywords: [下载, download, aria2, bt, magnet, 磁力, 种子, 多线程]
allowed-tools: Bash(python:scripts/cli.py)
---

# 下载管理器

基于 Aria2 引擎的多线程下载管理器。

## CLI 使用

```bash
# 启动 Aria2
python scripts/cli.py start

# 添加下载
python scripts/cli.py download "https://example.com/file.zip"
python scripts/cli.py download "magnet:?xt=urn:btih:..."
python scripts/cli.py download file.torrent

# 查看下载列表
python scripts/cli.py list

# 查看速度
python scripts/cli.py speed

# 暂停/恢复/删除
python scripts/cli.py pause <gid>
python scripts/cli.py resume <gid>
python scripts/cli.py remove <gid>

# 限速
python scripts/cli.py limit --download 1M --upload 500K

# 停止
python scripts/cli.py stop
```

## 前端 UI

集成到 Butler 玻璃拟态界面，`window.downloadManager.toggle()` 打开/关闭。
