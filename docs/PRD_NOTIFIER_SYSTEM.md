# PRD: Butler 智能事件提醒系统 (Notifier System)

## 1. 定位与目标
**Butler Notifier System** 是 Jarvis 系统的“中枢神经”，负责汇总并分发来自后端核心、底层硬件（C++ 调度器）以及各类技能模块（Skills）的实时提醒与授权请求。其目标是提供极致的视觉反馈、可靠的事件持久化以及安全的异步权限管理。

## 2. 核心特性
- **Apple-style Glassmorphism**: 界面采用毛玻璃效果、暗黑模式，并具备物理阴影。
- **呼吸感交互**: 弹窗具有平滑的入场与退场动画，默认 5-10 秒后自动消失。
- **全生命周期持久化**: 所有发出的提醒自动归档至 `data/notifications.db`。
- **音量自适应联动**: 发出提醒时，系统根据环境噪音级别自动微调音量。

## 3. 异步提权授权流程 (Asynchronous Authorization Flow)

这是系统安全性的核心。当 Skill 需要执行高危操作（如修改系统代码、调用 sudo 权限的工具）时，必须通过 Notifier 发起授权请求。

### 3.1 流程图描述
1.  **发起请求**: Skill 调用 `notifier.push`，在 `action_data` 中包含 `is_auth_request: true`。
2.  **注册回调**: Skill 在本地维护一个 `pending_actions` 映射，记录 `event_id` 及其对应的 `on_authorized` 与 `on_denied` 回调。
3.  **UI 呈现**: Notifier 通过 `event_bus` 将请求推送到前端。前端弹窗显示“允许”与“拒绝”按钮。
4.  **用户决策**: 用户点击按钮。
5.  **反馈回路**: 前端通过 BHL 协议或 Bridge 将决策发回后端。
6.  **触发回调**: `event_bus` 接收到反馈信号（如 `NOTIFICATION_RESPONSE`），Notifier 匹配 `event_id` 并触发 Skill 注册的回调函数。
7.  **执行**: 如果授权，Skill 执行高危代码；如果拒绝，Skill 记录日志并终止该任务。

### 3.2 伪代码演示
```python
# Skill 侧代码
def perform_secure_scan(self):
    event_id = self.request_permission(
        title="提权请求",
        content="Security Skill 请求使用 sudo 调用 nmap 进行内网扫描。",
        on_authorized=self._run_nmap_sudo,
        on_denied=self._abort_scan
    )

def _run_nmap_sudo(self, response_data):
    # 执行高危指令
    pass
```

## 4. 数据结构 (SQLite)
表名：`notifications`
- `id` (TEXT, PK): 唯一事件 ID。
- `title` (TEXT): 标题。
- `content` (TEXT): 正文。
- `priority` (INTEGER): 优先级 (0-3)。
- `source` (TEXT): 来源 (e.g., "sec_engineer")。
- `timestamp` (TEXT): 发生时间。
- `status` (TEXT): 状态 (active, closed, authorized, denied)。
- `action_data` (TEXT/JSON): 包含回调参数、授权标记等。

## 5. 视觉规范
- **左上角时间戳**: 每个弹窗固定位置显示精确到秒的发生时间。
- **自动关闭**:
    - 优先级 < 2: 5 秒自动关闭。
    - 优先级 >= 2: 10 秒自动关闭。
- **交互动作**: 点击弹窗可调出详情对话框。

## 6. 环境约束
- **Zero-dependency**: 后端逻辑层必须仅依赖 Python 标准库。
- **跨平台兼容**: 消息结构需兼容 Windows/Linux/macOS 的通知展示逻辑。
