# deploy/ — butler-dsh-adapter 安装与启动

仓库零二进制：产物由 CI（`.github/workflows/release.yml`）在打 `v*` tag 时构建并上传
GitHub Releases，安装脚本在安装期拉取，全部隔离进 `lib_external/`（便携模式，删目录即卸载）。

## 安装

```bash
# Linux / macOS（一行安装，自动拉取最新 Release）
bash deploy/install-dsh-adapter.sh

# 指定版本 / 镜像源 / 安装位置
bash deploy/install-dsh-adapter.sh --version v0.1.0 --prefix ./lib_external

# 无 Releases 网络场景：本地源码编译（要求 go + node/npm）
bash deploy/install-dsh-adapter.sh --from-source
```

```powershell
# Windows
.\deploy\install-dsh-adapter.ps1
.\deploy\install-dsh-adapter.ps1 -Version v0.1.0
```

内网镜像/加速：设 `BUTLER_DSH_BASE_URL` 环境变量指向镜像基址即可（下载 URL 格式：
`<base-url>/butler-dsh-connector_<tag>_<os-arch>.tar.gz` 等，同 Releases 布局）。

## 启动

```bash
bash deploy/start-dsh-adapter.sh -config connector.json
# Windows: lib_external\dsh-connector\butler-dsh-connector.exe -config connector.json
```

## 产物布局（安装后）

```
lib_external/
├── dsh-connector/
│   ├── butler-dsh-connector    # Go 连接器（静态单文件，零依赖）
│   ├── VERSION                 # 安装的版本 tag
│   ├── README.md / protocol.md
└── dsh-host/
    ├── dist/                   # DSH 宿主 shim（零运行时依赖）
    └── package.json
```

## 运行时依赖

| 组件 | 需要 |
|------|------|
| 连接器（Go） | 无（静态二进制） |
| DSH 宿主 shim | **Node.js ≥ 20** |
| 市场插件 | `butler skill install` 时按需下载 |

## 卸载

```bash
rm -rf lib_external/dsh-connector lib_external/dsh-host
```

## 发布流程（维护者）

1. `git tag v0.x.y && git push --tags`
2. CI 自动：Go/Node 全量测试 → 5 平台交叉构建（linux/darwin/windows × amd64/arm64）
   → shim 打包 → `SHA256SUMS` → 上传 Release
3. 用户侧安装脚本按平台拉取并校验 SHA-256
