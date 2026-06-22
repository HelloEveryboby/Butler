# Butler Spatial Matrix UI - 空间矩阵界面指南

Butler 3.0 采用了一套革命性的**空间矩阵 (Spatial Matrix)** 设计界面。该界面基于 HTML/CSS/JS 与 3D 变换技术，将功能模块分布在 $2 \times 2$ 的多维空间中，实现极致的极客质感。

![Butler Matrix UI](../assets/ui_2_0/matrix_chat.png)

## 核心设计理念

*   **空间象限驱动**：通过 `Ctrl + 方向键` 或双指滑动在四个功能象限间切换。
*   **毛玻璃 Dock 栏**：底部悬浮 Dock 提供快速导航与状态指示。
*   **物理动效 (Spring Physics)**：采用弹簧物理引擎，赋予拖拽与转场真实的阻尼感。
*   **无感流转 (AirDrop Pipeline)**：支持任务卡片向上“甩出”跨端流转。

---

## 象限说明

### 1. (0,0) 智能助手与多模态排障
系统的核心对话空间。
*   **激光扫描排障**：直接将报错截图拖入或粘贴，系统自动执行激光扫描 OCR 诊断。
*   **一键修复卡片**：诊断完成后弹出修复按钮，如“一键释放占用端口”。
*   **流式交互**：气泡式对话流，集成翻译、代码块与富媒体。

### 2. (1,0) DAG 可视化任务流水线
![Butler DAG View](../assets/ui_2_0/matrix_dag.png)
*   **拖拽构建**：从技能仓拖入卡片，自由布局。
*   **发光连接线**：动态贝塞尔曲线连接任务输入/输出点，具备发光呼吸特效。
*   **弹簧吸附**：卡片接近锚点时产生物理吸附感。

### 3. (0,1) 全局可观测时光机
![Butler Time Machine](../assets/ui_2_0/matrix_timemachine.png)
*   **状态回溯**：拖动底部时光滑块，全局 UI 进入“历史回放”模式。
*   **异常高亮**：回溯到故障发生点时，全屏呈现红色预警阴影，并自动定位报错日志。
*   **性能指标**：实时同步历史 CPU/内存 使用率视图。

### 4. (1,1) 模块化技能与文件仓
![Butler Skills View](../assets/ui_2_0/matrix_terminal.png)
*   **技能抽屉**：One Folder = One Skill 的卡片化管理。
*   **透明 Overlay**：
    *   **终端 (Terminal)**：高性能 `xterm.js` 叠加层，支持 PTY 交互。
    *   **备忘录 (Memos)**：毛玻璃半透明浮窗记录灵感。
*   **文件浏览器**：集成在侧边，支持拖拽文件进入流水线。

---

## 特色交互

### AirDrop 甩出流转
在任意可交互卡片上执行“向上快速滑动”或 `Shift + 点击`，卡片会伴随流光特效消失，并自动投递至局域网内的 Android 手机。

### 悬浮 Dock
位于屏幕底部的磨砂玻璃条：
*   **左侧图标**：象限快速跳转。
*   **活动点 (Dock Dot)**：指示当前所在的象限。
*   **右侧设置**：一键开启系统配置面板。

---

## 开发者说明

该前端通过 `pywebview` 与 Python 后端进行双向通信。
代码位置：
*   `frontend/view/index.html`: 矩阵结构
*   `frontend/view/style.css`: 玻璃拟态与 3D 变换
*   `frontend/view/matrix_controller.js`: 空间导航逻辑
*   `frontend/view/main.js`: 业务逻辑与桥接
*   `frontend/view/dag_engine.js`: DAG 渲染引擎
*   `frontend/view/time_machine_ui.js`: 时光机回溯逻辑
