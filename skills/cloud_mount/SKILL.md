---
id: cloud_mount
name: 网盘挂载本地硬盘
description: 将阿里云盘、百度网盘、OneDrive、Google Drive 等 30+ 网盘挂载为本地磁盘
version: 1.0.0
author: Butler
icon: fa-hard-drive
risk: low
keywords: [网盘, 挂载, 本地硬盘, alist, rclone, cloud, mount, 阿里云盘, 百度网盘, OneDrive]
allowed-tools: Bash(python:scripts/alist_manager.py), Bash(python:scripts/mount_manager.py)
---

# 网盘挂载本地硬盘

将 30+ 网盘服务挂载为本地磁盘，像操作本地文件一样操作云端文件。

## 支持的网盘

阿里云盘、百度网盘、OneDrive、Google Drive、夸克网盘、115网盘、
天翼云盘、移动云盘、阿里云 OSS、腾讯云 COS、MinIO、S3、
WebDAV、SFTP、FTP、SMB、群晖、坚果云……

## 使用方式

### 1. 启动 AList 服务
```bash
python scripts/alist_manager.py start
```

### 2. 添加网盘（通过 AList Web 管理界面）
启动后访问 http://localhost:5244/manage 登录管理后台添加存储

### 3. 挂载为本地磁盘
```bash
python scripts/mount_manager.py mount --letter Z
```

### 4. 卸载
```bash
python scripts/mount_manager.py unmount
```

## 架构

```
本地磁盘 (Z:) ──Rclone 挂载──▶ AList WebDAV (localhost:5244/dav)
                                    │
                        ┌───────────┼───────────┐
                        ▼           ▼           ▼
                    阿里云盘     百度网盘     OneDrive
```
