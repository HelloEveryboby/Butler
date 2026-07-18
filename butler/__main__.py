# -*- coding: utf-8 -*-
import sys

def main():
    # 检测是否在执行全新的 Butler v2.0 Alpha CLI 命令
    cli_commands = {"start", "agent", "package", "doctor", "tool"}

    # 如果第一个参数匹配，分发调用 v2.0 命令行主入口
    if len(sys.argv) > 1 and sys.argv[1] in cli_commands:
        from butler.cli.main import run_cli
        run_cli()
    else:
        # 完全延迟载入经典管理模式（Tkinter / 2x2 Matrix UI），避免污染 v2.0 命令行的极速导入
        from butler.butler_app import main as legacy_main
        legacy_main()

if __name__ == "__main__":
    main()
