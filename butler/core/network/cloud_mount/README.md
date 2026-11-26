# 网盘挂载本地硬盘 (Cloud Mount)

将 30+ 网盘服务挂载为本地磁盘，像操作本地文件一样操作云端文件。

## 工作原理

```
本地磁盘 (Z: 或 ~/butler-cloud)
    │
    ▼
Rclone (FUSE 挂载，提供本地文件系统接口)
    │
    ▼
AList WebDAV (localhost:5244/dav，聚合网关)
    │
    ├── 阿里云盘
    ├── 百度网盘
    ├── OneDrive
    ├── Google Drive
    ├── 夸克网盘
    ├── 115网盘
    ├── 天翼云盘
    ├── 阿里云 OSS
    ├── 腾讯云 COS
    ├── S3 / MinIO
    ├── WebDAV / SFTP / FTP / SMB
    └── ……30+ 种
```

## 快速开始

### 1. 检查前置条件
```bash
python scripts/mount_manager.py check
```

Windows 需要安装 [WinFSP](https://winfsp.dev/rel/)，macOS 需要安装 [macFUSE](https://osxfuse.github.io/)，Linux 自带 FUSE。

### 2. 启动 AList
```bash
python scripts/alist_manager.py start
```

首次启动会自动下载 AList 二进制。启动后访问 http://localhost:5244/manage 添加网盘。

### 3. 挂载为本地磁盘
```bash
# Windows: 挂载为 Z 盘
python scripts/mount_manager.py mount --letter Z

# Linux/macOS: 挂载到指定目录
python scripts/mount_manager.py mount --mount-point ~/butler-cloud
```

### 4. 使用
挂载后直接在文件管理器中访问，像本地磁盘一样读写文件。

### 5. 卸载
```bash
python scripts/mount_manager.py unmount
```

## 支持的网盘（AList）

完整列表见 [AList 官方文档](https://alist.nn.ci/zh/guide/)，主要包括：

| 类型 | 网盘 |
|------|------|
| 国内网盘 | 阿里云盘、百度网盘、夸克网盘、115网盘、天翼云盘、移动云盘、和彩云 |
| 国际网盘 | OneDrive、Google Drive、Dropbox、pCloud、Mega |
| 对象存储 | 阿里云 OSS、腾讯云 COS、华为云 OBS、AWS S3、MinIO |
| 协议 | WebDAV、SFTP、FTP、SMB |
| NAS | 群晖、威联通 |

## 文件结构

```
cloud_mount/
├── SKILL.md              # 技能描述
├── README.md             # 本文档
├── scripts/
│   ├── alist_manager.py  # AList 生命周期管理（下载/启动/停止/配置）
│   └── mount_manager.py  # Rclone 挂载管理（挂载/卸载/状态检查）
└── runtime/              # 运行时数据（自动创建）
    ├── alist/            # AList 二进制和数据
    │   ├── alist         # AList 可执行文件
    │   ├── data/         # AList 数据库和配置
    │   └── alist.log     # 日志
    └── rclone/           # Rclone 二进制和配置
        ├── rclone        # Rclone 可执行文件
        ├── rclone.conf   # 配置文件
        └── mount.log     # 挂载日志
```

## 配置说明

### AList 默认配置
- 地址: http://localhost:5244
- 管理后台: http://localhost:5244/manage
- WebDAV: http://localhost:5244/dav
- 用户名: admin
- 密码: 首次启动自动生成，查看日志或运行 `python scripts/alist_manager.py status`

### Rclone 挂载参数
- 缓存模式: writes（写入缓存，提升性能）
- 缓存有效期: 1 小时
- Windows 盘符: 默认 Z:
- Linux/macOS 挂载点: 默认 ~/butler-cloud
