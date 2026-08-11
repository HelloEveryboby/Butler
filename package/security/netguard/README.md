# NetGuard API — 重构版

网络安全 API 平台，面向安全研究人员。

## 目录结构

```
netguard/
├── app/
│   ├── config.py           # Pydantic Settings（环境变量驱动）
│   ├── database.py         # SQLAlchemy async 引擎 + 会话
│   ├── deps.py             # 统一依赖注入（JWT/API Key 双认证）
│   ├── exceptions.py       # 自定义异常 + 全局处理器
│   ├── models/             # ORM 模型（独立文件，JSON 列，外键）
│   ├── schemas/            # Pydantic 请求/响应模型
│   ├── services/           # 业务逻辑层（纯函数，可测试）
│   ├── routers/v1/         # 路由层（薄层，只做校验+调用 service）
│   ├── middleware/          # 请求日志等中间件
│   └── utils/              # 安全工具、网络校验
├── alembic/                # 数据库迁移
├── tests/                  # pytest 测试
├── main.py                 # FastAPI 工厂
├── run.py                  # 启动入口
└── pyproject.toml
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp config/.env.example .env
# 编辑 .env，填入 SECRET_KEY

# 3. 启动
python run.py

# 4. 访问 API 文档
open http://localhost:8000/docs
```

## 运行测试

```bash
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

## 数据库迁移

```bash
# 生成迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

## API 端点

| 模块 | 端点 | 说明 |
|------|------|------|
| 认证 | `POST /api/v1/auth/register` | 注册 |
| 认证 | `POST /api/v1/auth/login` | 登录 |
| 认证 | `GET /api/v1/auth/me` | 当前用户信息 |
| 威胁情报 | `GET /api/v1/threat-intel/lookup` | 查询目标信誉 |
| 扫描 | `POST /api/v1/scan/port-scan` | 端口扫描 |
| 扫描 | `POST /api/v1/scan/vuln-probe` | 漏洞探测 |
| 流量 | `POST /api/v1/traffic/analyze` | 数据包分析 |
| 防护 | `POST /api/v1/protection/analyze` | 请求安全分析 |
| 防护 | `GET /api/v1/protection/blocked-ips` | 已阻断 IP |
| 统计 | `GET /api/v1/stats/dashboard` | 仪表盘 |

## 认证方式

支持两种认证方式（优先 API Key）：

```bash
# JWT Bearer Token
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/auth/me

# API Key
curl -H "X-API-Key: <key>" http://localhost:8000/api/v1/auth/me
```

## 相对原版的改进

- **配置安全化**：SECRET_KEY 强制配置，无默认值
- **CORS 白名单**：不再 `allow_origins=["*"]`
- **数据库迁移**：引入 Alembic，支持 schema 演进
- **JSON 列**：`categories`/`details`/`results` 用原生 JSON 列替代 Text+手动序列化
- **外键约束**：所有 `user_id` 建立 ForeignKey 关系
- **Service 层**：Router → Service → DB 三层分离
- **Scanner 全异步**：移除同步 `socket` 调用，全部 `asyncio.open_connection`
- **SSRF 防护**：扫描目标校验，禁止内网扫描
- **双认证**：JWT + API Key 均可访问
- **确定性评分**：移除 `random`，相同输入永远相同输出
- **漏洞检测修复**：`potential_vulnerabilities` 不再永远为空
- **请求日志**：APICallLog 表实际写入
- **测试覆盖**：核心接口均有 pytest 测试
