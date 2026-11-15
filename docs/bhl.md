# BHL — 混合语言链路（C / C++ / Go / Rust）

Butler 的混合编程不再是「源码躺在 programs/ 里、Python 只用回退实现」。
现在有一条统一的链路：**manifest 声明 → 编译 → 方法路由 → 子进程 JSON-RPC → 统一信封**。

## 结构

```text
Agent / CLI / Python 代码
        │  hub.call("factorize", {"number": 91})
        ▼
   HybridHub  ── 方法索引（method -> [模块]）
        │         ├─ 懒启动 worker（stdio JSON-RPC）
        │         ├─ 超时 / 崩溃 → 重启或换下一个模块
        │         └─ 没有原生模块 → hybrid_fallbacks（via="fallback"）
        ▼
 programs/<module>/<executable>     C / C++ / Go / Rust
```

调用结果统一为：

```json
{"ok": true, "method": "factorize", "module": "hybrid_compute",
 "language": "cpp", "via": "native:cpp", "result": {"factors": [7, 13]}, "elapsed_ms": 2.1}
```

`via` 明确区分 `native:<语言>` 与 `fallback`，不会再出现「看起来成功、其实是假数据」。

## 命令

```bash
butler hybrid status                 # 各模块：语言 / 是否已构建 / 是否运行 / 方法
butler hybrid build                  # 按 manifest 构建全部（缺工具链的自动跳过）
butler hybrid build hybrid_crypto --force
butler hybrid call factorize --params '{"number": 91}'
butler hybrid call hash_sha256 --module hybrid_crypto --params '{"text":"butler"}'
```

构建命令来自各模块自己的 `manifest.json`（`build` / `build_command` / `entry.executable` 三种写法都兼容）。

## 新增一个模块：`butler hybrid new`

```bash
butler hybrid new image_ops --lang cpp
butler hybrid build image_ops
butler hybrid call ping --module image_ops
```

支持 `c` / `cpp` / `go` / `rust` / `python`。生成器会写好：

* `manifest.json`（语言、构建命令、可执行文件、方法表）
* 一个能跑的最小 stdio worker（`ping` / `echo` / `exit`）

生成后不用改任何 Python 代码，`HybridHub` 会自动发现并路由。

## 一次性 CLI 工具：`protocol: "cli"`

不是常驻 worker 的现成工具，用 `"protocol": "cli"` 声明 argv 模板即可接入：

```json
{
  "name": "word_counter",
  "language": "c",
  "protocol": "cli",
  "executable": "word_counter_exec",
  "build": "gcc -O2 -std=c99 word_counter.c counter.c -o {output}",
  "methods": {
    "count_words": { "argv": ["{path}"] }
  }
}
```

`{}` 里的占位符来自调用参数，进程的 stdout 作为结果返回。

## Agent 工具

AgentRuntime 自动注册两个工具：

* `native_call`：`{"method": "...", "params": {...}, "module": "可选"}`
* `native_status`：查看模块构建/运行状态

因此 LLM 可以自己决定「这段计算交给 C++」「哈希交给 Rust」「并发扫描交给 Go」。

## 已接入的模块

| 模块 | 语言 | 方法 |
| --- | --- | --- |
| hybrid_sysutil | C | get_system_info, list_processes, grep_search, glob_list, patch_edit, detect_displays, check_connections |
| hybrid_compute | C++ | factorize, fibonacci |
| hybrid_math | C++ | get_stats, matrix_test |
| hybrid_doc_processor | C++ | analyze_file |
| hybrid_vision | C++ | process_test |
| hybrid_memory | Go | search, get_stats |
| hybrid_net | Go | check_network, scan_ports, batch_ping, benchmark, concurrent_download |
| hybrid_system_executor | Go | audit, log_scan, remote_dispatch, discover_nodes, get_stats |
| hybrid_memos | Go | add_memo, list_memos, search_memos, update_memo, delete_memo |
| hybrid_crypto | Rust | hash_sha256, hash_file, encrypt_file, decrypt_file |
| word_counter | C（CLI） | count_words |
| hybrid_archive | C++（CLI） | stream_replace |

同名方法（例如 `get_stats`）用 `--module` 显式指定。

## 工具链与限制

* 需要 `gcc` / `g++` / `go` / `cargo`；缺少时 `build` 会跳过并说明原因。
* Rust 模块已把 `edition` 调整为 2021、`Cargo.lock` 版本降为 3，兼容 rustc 1.75；更新的工具链也能构建。
* `hybrid_memos` 依赖 cgo + sqlite3，且 `go.mod` 要求新工具链，需要能访问 Go 模块代理。
* 仓库里自带的 `processor` / `executor_service` 是旧的预编译二进制，架构不匹配时用
  `butler hybrid build <module> --force` 重编即可。
* `bcli` 是 STM32 串口控制器，不通过 stdio 工作，不在路由表内。
* HTTP/FFI 形式的第三方库还不能直接接；需要先包一层 stdio worker 或 CLI。
