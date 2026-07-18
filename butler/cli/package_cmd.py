# -*- coding: utf-8 -*-
from butler.package_runtime.loader import PackageLoader

def list_packages():
    """
    列出所有已安装的 AI 技能和数字员工包。
    """
    loader = PackageLoader()
    packages = loader.registry.list_packages()

    print("\n==============================================")
    print("            已安装的 Butler 技能/员工包       ")
    print("==============================================")
    if not packages:
        print("暂无已安装注册的包记录。")
    else:
        for p in packages:
            print(f"📦 名称: {p['name']:<18} | 版本: {p['version']:<8} | 状态: {p['status']}")
            manifest = loader.get_manifest(p['name'])
            if manifest:
                print(f"   - 类型: {manifest.type} | 系统权限限制: {', '.join(manifest.permissions) or '无'}")
    print("==============================================\n")

def install_package(path: str):
    """
    安装指定的本地包（包含有效的 manifest.json）。
    """
    loader = PackageLoader()
    print(f"[*] 正在尝试从源路径安装包: {path}")
    if loader.install(path):
        print(f"✅ 安装并成功注册新技能包！")
    else:
        print("❌ 安装失败。请检查该路径及 manifest.json 清单配置是否正确。")
