---
name: clipboard_history
description: 剪贴板历史记录核心插件。在本地异步监听/记录系统剪贴板变更，将其安全加密后存储到本地。
provides:
  - system.clipboard.history
requires: {}
risk: low
---

# 剪贴板安全历史 (Clipboard History)

本插件提供本地优先、高度安全的剪贴板历史回溯服务。

## 核心能力
1. **自动变更捕获**：周期性轮询系统剪贴板（基于 Tkinter / OS 剪贴板 API 优雅 Fallback），检测到最新文本自动记录。
2. **敏感内容加密**：利用 `Crypto.Cipher.AES` 对存储在本地的剪贴板条目进行高级 AES-CBC 加密保护，防止其他进程刺探。
3. **滚动缓存（Rolling Cache）**：默认最多保持 15 条最近的历史条目，防止内存/磁盘无节制增长。
