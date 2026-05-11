---
name: Music_Module
description: 音乐播放技能，支持本地文件、URL流媒体、环境自适应音量以及专注模式。
version: 1.0.0
author: Jules
actions:
  - name: play
    description: 播放指定路径或URL的音乐。
    params:
      path: 音乐文件路径或URL。
      runner: (可选) 指定执行的 Runner ID。
  - name: pause
    description: 暂停/恢复当前播放。
  - name: volume
    description: 设置音量 (0-100)。
  - name: next
    description: 下一首。
  - name: extract_color
    description: 从封面图提取主色调。
---

# 音乐模块 (Music Module)

这是 Butler 的轻量化音频播放模块，核心引擎基于 C++ 编写，集成在 Butler-Runner 中。

## 功能特性
1. **轻量化播放**：极低的内存占用，支持流式解码。
2. **环境自适应 (DRC)**：根据 HardwareManager 提供的环境噪音，自动补偿音乐增益。
3. **专注模式**：监测到编码活动（VS Code, PyCharm 等）时，自动切换到低频背景音。
4. **频谱可视化**：C++ 实时计算 FFT 频谱并推送至前端。
5. **毛玻璃视觉**：支持从封面图提取色彩并应用于 UI 背景。

## 配置
在 `config.yaml` 中配置默认 Runner 和专注模式音源：
```yaml
skills:
  music_module:
    default_runner: "cpp_runner"
    focus_bgm_url: "http://your-lofi-stream-url"
```
