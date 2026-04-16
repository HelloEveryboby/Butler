#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import os
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 加载本地外部库
lib_path = project_root / "lib_external"
if lib_path.exists():
    import site
    site.addsitedir(str(lib_path))

def main():
    parser = argparse.ArgumentParser(
        description="Butler 统一命令行入口 (CLI) - 极客与专业用户的利器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python butler_cli.py crawl --url http://example.com
  python butler_cli.py email --send --to user@example.com --subject "Hello" --body "World"
  python butler_cli.py image-search --query "猫咪"
  python butler_cli.py encrypt --path secret.txt --algo AES
  python butler_cli.py translate --text "Hello world"
  python butler_cli.py monitor
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    # 1. 爬虫 (Crawl)
    crawl_parser = subparsers.add_parser("crawl", help="网页数据爬取与搜索")
    crawl_parser.add_argument("--url", help="直接爬取的网页地址")
    crawl_parser.add_argument("--query", help="通过搜索引擎搜索并爬取的关键词")
    crawl_parser.add_argument("--type", choices=["image", "video"], default="image", help="资源类型 (默认: image)")

    # 2. 邮件 (Email)
    email_parser = subparsers.add_parser("email", help="邮箱助手：发送、接收与管理")
    email_parser.add_argument("--send", action="store_true", help="发送新邮件")
    email_parser.add_argument("--receive", action="store_true", help="检查未读邮件")
    email_parser.add_argument("--to", help="收件人地址")
    email_parser.add_argument("--subject", help="邮件主题")
    email_parser.add_argument("--body", help="邮件正文")

    # 3. 图片搜索 (Image Search)
    img_parser = subparsers.add_parser("image-search", help="图片搜索与识别")
    img_parser.add_argument("--query", help="关键词搜图")
    img_parser.add_argument("--path", help="本地图片或文件夹路径")
    img_parser.add_argument("--mode", choices=["local", "batch"], default="local", help="本地模式 (local) 或 批量以图搜图 (batch)")

    # 4. 加解密 (Crypto)
    enc_parser = subparsers.add_parser("encrypt", help="对称加密文件")
    enc_parser.add_argument("--path", required=True, help="待加密文件路径")
    enc_parser.add_argument("--algo", choices=["AES", "DES"], default="AES", help="加密算法")

    dec_parser = subparsers.add_parser("decrypt", help="对称解密文件")
    dec_parser.add_argument("--path", required=True, help="待解密文件路径")
    dec_parser.add_argument("--algo", choices=["AES", "DES"], default="AES", help="解密算法")

    # 5. 天气 (Weather)
    weather_parser = subparsers.add_parser("weather", help="实时天气查询")
    weather_parser.add_argument("city", help="城市名称 (如: 北京)")

    # 6. 文件转换 (Convert)
    convert_parser = subparsers.add_parser("convert", help="文档/图片格式转换")
    convert_parser.add_argument("--input", required=True, help="输入文件路径")
    convert_parser.add_argument("--output", required=True, help="输出文件路径")

    # 7. 翻译 (Translate)
    trans_parser = subparsers.add_parser("translate", help="多模态智能翻译")
    trans_parser.add_argument("--text", help="待翻译文字")
    trans_parser.add_argument("--file", help="待翻译文件路径")
    trans_parser.add_argument("--url", help="待翻译网页地址")

    # 8. 系统监控 (Monitor)
    subparsers.add_parser("monitor", help="系统健康监控与自愈报告")

    # 9. 系统审计 (Audit)
    audit_parser = subparsers.add_parser("audit", help="高性能系统审计与调度演示")
    audit_parser.add_argument("--dir", help="审计目标目录")

    # 10. 依赖管理 (Dependency)
    dep_parser = subparsers.add_parser("dependency", help="项目环境与依赖库管理")
    dep_parser.add_argument("op", choices=["install", "install_all", "setup_runtime"], help="操作类型")
    dep_parser.add_argument("--package", help="特定的包名 (仅用于 install 操作)")

    # 11. 文件管理 (File)
    file_parser = subparsers.add_parser("file", help="基础文件操作")
    file_parser.add_argument("--op", choices=["create", "read", "delete", "list"], required=True, help="操作类型")
    file_parser.add_argument("--path", required=True, help="目标路径")
    file_parser.add_argument("--content", help="写入的内容 (仅用于 create)")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    try:
        if args.command == "crawl":
            from package.network.crawler import run as crawl_run
            crawl_run(url=args.url, search_query=args.query, type=args.type)

        elif args.command == "email":
            from package.network.e_mail import EmailAssistant
            assistant = EmailAssistant()
            if args.send:
                if not args.to or not args.subject or not args.body:
                    print("❌ 错误: 发送邮件需要 --to, --subject 和 --body 参数。")
                else:
                    assistant.send_email(args.subject, args.body, args.to)
            elif args.receive:
                emails = assistant.fetch_unread_emails()
                assistant.display_emails(emails)
            else:
                print("ℹ️ 请指定 --send 或 --receive。")

        elif args.command == "image-search":
            from package.network.image_search_tool import run as img_run
            img_run(query=args.query, path=args.path, mode=args.mode)

        elif args.command == "encrypt":
            from package.security.encrypt import DualLayerEncryptor, SecureVault
            import getpass
            core_code = getpass.getpass("请输入 6 位核心码: ")
            DualLayerEncryptor().encrypt_file(args.path, core_code)

        elif args.command == "decrypt":
            from package.security.encrypt import DualLayerEncryptor, SecureVault
            import getpass
            core_code = getpass.getpass("请输入 6 位核心码: ")
            DualLayerEncryptor().decrypt_file(args.path, core_code)

        elif args.command == "weather":
            from package.network.weather import get_weather_from_web
            res = get_weather_from_web(args.city)
            if res:
                print(f"☀️ {args.city} 天气状况:")
                for k, v in res.items():
                    print(f"  {k}: {v}")
            else:
                print("❌ 无法获取天气信息。")

        elif args.command == "convert":
            from package.document.file_converter import run as conv_run
            conv_run(input_file=args.input, output_file=args.output)

        elif args.command == "translate":
            from package.document.translators import translate_text, translate_file, translate_website
            if args.text:
                print(f"🌐 翻译结果:\n{translate_text(args.text)}")
            elif args.file:
                output = args.file + ".translated.txt"
                translate_file(args.file, output)
            elif args.url:
                translate_website(args.url)
            else:
                print("ℹ️ 请提供 --text, --file 或 --url。")

        elif args.command == "monitor":
            from package.core_utils.health_monitor import run as monitor_run
            monitor_run()

        elif args.command == "audit":
            from package.core_utils.system_executor_tool import run as audit_run
            audit_run(dir=args.dir)

        elif args.command == "dependency":
            from package.core_utils.dependency_manager import run as dep_run
            result = dep_run(command=args.op, package=args.package)
            print(result)

        elif args.command == "file":
            from package.file_system.file_manager import FileManager
            fm = FileManager()
            if args.op == "create":
                success, msg = fm.create_file(args.path, args.content or "")
                print(msg)
            elif args.op == "read":
                success, content = fm.read_file(args.path)
                print(content if success else f"❌ {content}")
            elif args.op == "delete":
                success, msg = fm.delete_file(args.path)
                print(msg)
            elif args.op == "list":
                success, items = fm.list_directory(args.path)
                if success:
                    print(f"📂 {args.path} 中的内容:")
                    for item in items: print(f"  - {item}")
                else:
                    print(f"❌ {items}")

    except Exception as e:
        print(f"💥 执行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
