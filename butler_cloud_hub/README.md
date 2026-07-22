# Butler Cloud Hub — 本地集成版

> 多网盘统一管理，直接嵌入 Butler，不开 HTTP 服务，不依赖浏览器。

## 架构

```
Butler 主程序 (butler_app.py)
    │
    ├── ModernBridge (pywebview)
    │       │
    │       ├── cloud_list_storages()  → JSON
    │       ├── cloud_list_files()     → JSON
    │       ├── cloud_search()         → JSON
    │       ├── cloud_add_storage()    → JSON
    │       └── cloud_transfer()       → JSON
    │
    ├── LocalCloudHub
    │       │
    │       ├── CloudHub (管理器)
    │       │     ├── AliyunDriver    阿里云盘
    │       │     ├── BaiduDriver     百度网盘
    │       │     ├── OneDriveDriver  OneDrive
    │       │     ├── WebDAVDriver    WebDAV
    │       │     └── LocalDriver     本地文件
    │       │
    │       └── ~/.butler/cloud.json  配置文件
    │
    └── 前端 (WebView)
            │
            └── CloudBrowser.ts  统一文件浏览器
                    │
                    └── window.pywebview.api.cloud_xxx()
```

## 使用方式

### 1. 在 Butler 中集成

```python
# butler_app.py 或 modern_app.py 中
from butler_cloud_hub.local_hub import LocalCloudHub

cloud = LocalCloudHub()
cloud.init()

# 暴露给前端
class ModernBridge:
    def __init__(self):
        self.cloud = cloud

    def cloud_list_storages(self):
        return self.cloud.list_storages()

    def cloud_list_files(self, storage, path="/"):
        return self.cloud.list_files(storage, path)

    def cloud_search(self, keyword, storage=None):
        return self.cloud.search(keyword, storage)
```

### 2. 前端调用

```typescript
// 通过 pywebview 直接调用 Python
const api = window.pywebview.api;

// 列出存储
const storages = JSON.parse(api.cloud_list_storages());

// 列出文件
const files = JSON.parse(api.cloud_list_files("我的阿里云盘", "/照片"));

// 搜索
const results = JSON.parse(api.cloud_search("报告"));

// 跨盘传输
api.cloud_transfer("阿里云盘", "/photo.jpg", "百度网盘", "/backup/photo.jpg");
```

### 3. 配置文件

`~/.butler/cloud.json`:

```json
[
  {
    "name": "我的阿里云盘",
    "type": "aliyun",
    "config": {
      "refresh_token": "..."
    },
    "enabled": true,
    "read_only": false
  },
  {
    "name": "公司 NAS",
    "type": "webdav",
    "config": {
      "url": "https://nas.example.com/dav",
      "username": "user",
      "password": "pass"
    },
    "enabled": true,
    "read_only": false
  }
]
```

## 支持的存储

| 驱动 | 类型标识 | 认证方式 |
|------|---------|---------|
| 本地文件系统 | `local` | root 路径 |
| 阿里云盘 | `aliyun` | refresh_token |
| 百度网盘 | `baidu` | access_token |
| OneDrive | `onedrive` | OAuth2 (client_id + refresh_token) |
| WebDAV | `webdav` | URL + 用户名密码 |

## 添加新驱动

1. 在 `drivers/` 下创建 `xxx_driver.py`
2. 实现 `StorageDriver` 接口的所有方法
3. 在 `drivers/hub.py` 的 `_load_drivers()` 中注册
4. 在 `StorageType` 枚举中添加类型

```python
# drivers/xxx_driver.py
from .base import StorageDriver, StorageConfig, FileItem

class XxxDriver(StorageDriver):
    async def connect(self) -> bool: ...
    async def disconnect(self) -> None: ...
    async def list(self, path: str) -> list[FileItem]: ...
    async def stat(self, path: str) -> FileItem: ...
    async def get(self, path: str) -> bytes: ...
    async def put(self, path: str, data: bytes) -> FileItem: ...
    async def delete(self, path: str) -> None: ...
    async def mkdir(self, path: str) -> None: ...
    async def move(self, src: str, dst: str) -> None: ...
    async def copy(self, src: str, dst: str) -> None: ...
```

## 文件清单

```
butler-cloud-hub/
├── __init__.py              # 包入口
├── local_hub.py             # 本地集成版 Hub (核心)
├── integration_example.py   # ModernBridge 集成示例
├── README.md
├── drivers/
│   ├── __init__.py
│   ├── base.py              # 抽象接口 + 数据模型
│   ├── hub.py               # CloudHub 管理器
│   ├── local_driver.py      # 本地文件系统
│   ├── aliyun_driver.py     # 阿里云盘
│   ├── baidu_driver.py      # 百度网盘
│   ├── onedrive_driver.py   # OneDrive
│   └── webdav_driver.py     # WebDAV
└── ui/
    └── CloudBrowser.ts      # 前端文件浏览器
```
