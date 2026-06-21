# Butler 一键启动指南

## 快速开始

### Windows
```bash
cd Butler
bin\run_setup.bat
```

### Linux / macOS
```bash
cd Butler
chmod +x bin/run_setup.sh
./bin/run_setup.sh
```

## 启动流程说明

### 第一次运行
当你第一次运行 Butler 时，系统会依次执行以下步骤：

1. **启动向导** (`StartupWizard`)
   - 检查系统环境
   - 自动安装依赖
   - 显示进度条和日志

2. **配置向导** (`EnhancedConfigWizard`)
   - 输入 API 密钥
   - 验证密钥有效性
   - 保存配置

3. **应用启动**
   - 加载配置
   - 初始化服务
   - 进入主界面

### 后续运行
之后每次运行 Butler 时，系统会：

1. 检查配置文件
2. 验证 API 密钥（如果缺失则显示配置向导）
3. 直接启动应用

## 新增功能

### 1. 启动向导 (`StartupWizard`)
- 显示详细的初始化进度
- 自动安装依赖
- 进度条反馈
- 错误处理和重试

### 2. 增强的配置向导 (`EnhancedConfigWizard`)
- 支持 API 密钥测试
- 状态指示器��✅/❌）
- 详细的错误提示
- 支持跳过非必需配置

### 3. 统一配置管理 (`ConfigManager`)
- 统一处理 .env 和 YAML 配置
- 支持运行时配置修改
- 自动持久化
- 配置验证

### 4. 设置管理 (`SetupManager`)
- 依赖自动检查和安装
- 首次运行检测
- 进度回调
- 完整的错误处理

## 文件结构

```
Butler/
├── butler/
│   ├── gui/
│   │   ├── config_wizard_enhanced.py  # 增强的配置向导
│   │   ├── startup_wizard.py          # 启动向导
│   │   └── __init__.py
│   ├── core/
│   │   ├── config_manager.py          # 统一配置管理
│   │   └── setup_manager.py           # 设置管理
│   ├── butler_app_enhanced.py         # 增强的启动文件
│   └── butler_app.py                  # 原始主应用（兼容）
├── bin/
│   ├── run_setup.bat                  # Windows 设置脚本
│   ├── run_setup.sh                   # Linux/macOS 设置脚本
│   ├── run.bat                        # Windows 快速启动
│   └── run.sh                         # Linux/macOS 快速启动
└── SETUP_GUIDE.md                     # 本文件
```

## 故障排查

### 问题：Python 未找到
**解决方案**：确保已安装 Python 3.8+ 并添加到系统 PATH

### 问题：依赖安装失败
**解决方案**：
- 检查网络连接
- 尝试手动运行：`python -m pip install -r requirements.txt`
- 使用便携模式：`python -m package.core_utils.dependency_manager install_all`

### 问题：API 密钥验证失败
**解决方案**：
- 检查密钥是否正确复制
- 确保网络连接正常
- 验证 API 服务是否可用
- 在 https://platform.deepseek.com 检查账户状态

### 问题：配置文件冲突
**解决方案**：
- 系统会自动优先使用 .env 文件
- 如需使用 YAML，删除或重命名 .env
- 使用 `ConfigManager` 的统一接口管理配置

## 开发者指南

### 自定义初始化流程
```python
from butler.core.setup_manager import setup_manager
from butler.gui.startup_wizard import StartupWizard

# 检查首次运行
if setup_manager.check_first_run():
    wizard = StartupWizard()
    wizard.run()

# 手动运行特定步骤
setup_manager.install_dependencies(progress_callback=my_callback)
```

### 使用统一配置管理
```python
from butler.core.config_manager import config_manager

# 获取配置
api_key = config_manager.get('api.deepseek_key')

# 设置配置
config_manager.set('api.deepseek_key', 'sk-xxx')

# 验证必需的密钥
is_valid, missing_keys = config_manager.validate_required_keys()
```

## 许可证

MIT License - 详见 LICENSE 文件
