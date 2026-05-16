---
id: archive_manager
name: 压缩管理 (Archive Manager)
description: 管理压缩包内容，支持文件改动自动探测、原子更新与原子替换，保障压缩包数据的一致性。
author: Butler Team
version: 2.0.0
tags: [system, tool, archive]
tools:
  - name: list_zip_contents
    description: 列出压缩包内的所有文件列表。
    parameters:
      zip_path: (required) 压缩包的绝对路径。
  - name: open_zip_file
    description: 解压压缩包中的特定文件并调用系统默认程序打开，同时启动改动追踪。
    parameters:
      zip_path: (required) 压缩包路径。
      file_in_zip: (required) 压缩包内的文件路径。
  - name: detect_changes
    description: 探测已打开的文件是否发生了改动（基于 MD5 校验）。
    parameters:
      extracted_path: (required) 已解压文件的本地缓存路径。
  - name: sync_zip_file
    description: 将改动后的文件同步回原压缩包（原子替换）。
    parameters:
      extracted_path: (required) 本地缓存路径。
      action: (optional) 'Y' 同步, 'N' 取消并清理。
---

# 压缩管理技能 (Archive Manager Skill)

该技能提供了一套完整的压缩包管理方案，特别是针对“打开-编辑-保存回压缩包”这一复杂工作流进行了优化。

### 核心功能

1. **列表查看**：快速预览 `.zip` 文件内部结构。
2. **实时追踪**：当通过该技能打开压缩包内的文件时，系统会自动在后台建立 MD5 指纹。
3. **静默同步**：探测到文件保存后，支持一键原子式地将新内容写回压缩包，无需手动删除再添加。

### 使用示例

- "列出 `D:/data.zip` 里的文件"
- "打开 `backup.zip` 里的 `config.yaml`"
- "我改好了，同步回压缩包"

### 注意事项

- 暂仅支持 `.zip` 格式。
- 修改大文件时，由于需要重建压缩包，可能会有短暂的进度条提示。
