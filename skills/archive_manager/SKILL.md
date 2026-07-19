---
id: archive_manager
name: 高性能压缩管理 (Archive Manager v2.0 - Powered by 7-Zip)
description: 深度融合高性能 7-Zip 原生内核，提供极致极速的归档管理。支持 .7z, .zip, .tar, .gz 等多格式，提供 AES-256 高强度加密、分卷分割压缩与流式解压合并。同时支持文件编辑改动自动追踪与静默原子更新。
author: Butler Team
version: 2.1.0
tags: [system, tool, archive, 7zip]
risk: low
provides:
  - archive.managed
requires: {}
isolation: process
tools:
  - name: list_contents
    description: 列出压缩包或归档文件内的完整文件和目录列表。支持 .7z, .zip, .tar, .gz 等。
    parameters:
      archive_path: (required) 压缩包的绝对路径。
  - name: compress
    description: 高性能流式压缩文件或目录。支持多格式、AES-256 加密保护、分卷切分。
    parameters:
      archive_path: (required) 生成的压缩包输出路径。
      targets: (required) 需要压缩的文件或目录列表（List[str]）。
      password: (optional) 加密密码。若格式为 .7z，将自动对文件名进行高强度加密。
      volume_size: (optional) 分卷压缩切分大小（如 10m, 100m）。
  - name: extract
    description: 高性能流式解压任何支持的压缩包格式。支持密码解包、分卷自动合并解包。
    parameters:
      archive_path: (required) 需要解压的压缩包路径。
      output_dir: (optional) 目标解压目录。默认解压至同名目录下。
      password: (optional) 解压所需的密码。
  - name: open_file
    description: 解压归档中的特定文件，调用系统关联程序打开，并启动后台 MD5 变动追踪。
    parameters:
      archive_path: (required) 压缩包的绝对路径。
      file_in_zip: (required) 压缩包内部的文件路径。
  - name: detect_changes
    description: 检测已打开并追踪的本地临时缓存文件是否发生了改动（基于 MD5 校验）。
    parameters:
      extracted_path: (required) 本地已解压缓存文件的绝对路径。
  - name: sync_file
    description: 将已修改的本地临时缓存文件安全、流式地写回原压缩包中（原子替换）。
    parameters:
      extracted_path: (required) 本地缓存文件的绝对路径。
      action: (optional) 'Y' 同步写回（默认），'N' 取消同步并清理缓存。
---

# 高性能压缩管理技能 (Archive Manager Skill - Powered by 7-Zip)

该技能提供了一套完整的、极高性能的本地压缩包管理方案。底层采用原生 C/C++ 编译的 7-Zip (7zz) 引擎进行流式数据包计算，既能压榨出极致的速度，又能实现极低内存和资源的常驻。

### 核心升级特性

1. **多格式万能支持**：原生处理 `.7z`, `.zip`, `.tar`, `.gz` 等归档格式，彻底打破单格式限制。
2. **AES-256 密码安全防护**：全面支持密码压缩与解包。对于 `.7z` 格式，默认启用 header 加密（加密文件名），防范一切越权窥视。
3. **分卷压缩与解包**：完美支持大文件切分为指定大小的分卷（如 `50m` / `100m`），解包时只需传入首卷（`.001`）即可实现自动多线程极速解包。
4. **低内存流式操作**：大文件处理期间全部采用流式 I/O，最大运行期内存常驻低于 10MB，保护宿主机免于 OOM 崩溃。
5. **打开-编辑-保存 静默原子更新**：保留并升级了文件追踪引擎。当你双击压缩包内某个文档编辑并保存后，系统可自动探测、原子流式替换回原压缩包，完美保障数据一致性。

### 常用指令示例

- "Butler，帮我把当前目录下的 reports/ 文件夹压缩成 7z 格式，加上密码 'Secret123'"
- "把 archive.tar.gz 解包到 /tmp/data 下"
- "列出 `D:/backups/db.7z` 里的所有内容"
- "我刚刚编辑好了 `config.json`，帮我同步回压缩包内"
