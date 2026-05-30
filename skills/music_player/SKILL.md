---
id: music_player
name: 音乐播放器
description: 提供 Apple 级质感的音乐播放体验，支持歌单管理、拖拽重排与状态同步。
version: 1.0.0
author: Butler
actions:
  - name: get_playlist
    description: 获取当前播放列表及其顺序。
  - name: update_order
    description: 更新播放列表顺序并持久化。
    parameters:
      - name: new_id_list
        type: list
        description: 新的歌曲 ID/路径 顺序列表。
  - name: play
    description: 播放指定索引或当前的音乐。
    parameters:
      - name: index
        type: integer
        required: false
  - name: pause
    description: 暂停当前播放。
  - name: next
    description: 下一首。
  - name: prev
    description: 上一首。
---

# 音乐播放器技能 (MusicSkill)

本技能是 Butler 核心音乐功能的标准化接口，负责前端 UI 与后端 C++/Python 播放引擎之间的状态协调。

## 核心职责
1. **状态同步**：确保前端旋转光碟的状态与后端实际播放进度严格对齐。
2. **持久化排列**：当用户在前端完成拖拽重排后，立刻将 `new_id_list` 写入 `music_library.json`。
3. **播放控制**：封装底层的播放、暂停、切歌逻辑。

## 交互规范
- 前端通过 `ModernBridge` 调用本技能的 `update_order`。
- 本技能在状态变更时，通过事件总线通知全系统。
