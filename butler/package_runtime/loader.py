# -*- coding: utf-8 -*-
import os
import sys
import json
import importlib.util
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from butler.package_runtime.manifest import PackageManifest
from butler.package_runtime.registry import PackageRegistry

class PackageLoader:
    """
    负责 AI 技能和数字员工包的安装、动态热加载和卸载管理。
    所有包被保存在本地磁盘目录 `butler/data/installed_packages/` 中。
    """
    def __init__(self, storage_dir: str = None, db_path: str = None):
        current_dir = Path(__file__).resolve().parent

        if storage_dir is None:
            self.storage_dir = current_dir.parent / "data" / "installed_packages"
        else:
            self.storage_dir = Path(storage_dir)

        self.registry = PackageRegistry(db_path=db_path)
        self._ensure_storage_and_defaults()
        self._auto_register_unregistered_packages()

    def _ensure_storage_and_defaults(self):
        """
        创建物理存储目录，并预置默认的演示包（如 demo-agent、email-reader），
        确保系统冷启动时即内置开箱即用的工作场景。
        """
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 1. 自动生成 demo-agent (演示数字员工包)
        demo_agent_dir = self.storage_dir / "demo-agent"
        if not demo_agent_dir.exists():
            demo_agent_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "name": "demo-agent",
                "version": "1.0.0",
                "type": "agent",
                "permissions": ["filesystem.read", "network"],
                "entry": "main.py",
                "dependencies": {}
            }
            (demo_agent_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

            entry_code = """# -*- coding: utf-8 -*-
def run(input_data=None, **kwargs):
    print("【数字员工】正在执行演示任务...")
    return {
        "status": "success",
        "message": f"数字员工任务运行成功。已接收输入: {input_data}",
        "result": "自动化数据分析已完成。"
    }
"""
            (demo_agent_dir / "main.py").write_text(entry_code, encoding="utf-8")
            self.registry.register("demo-agent", "1.0.0", "active")

        # 2. 自动生成 email-reader (演示邮件抓取技能包)
        email_reader_dir = self.storage_dir / "email-reader"
        if not email_reader_dir.exists():
            email_reader_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "name": "email-reader",
                "version": "1.1.0",
                "type": "skill",
                "permissions": ["network"],
                "entry": "main.py",
                "dependencies": {}
            }
            (email_reader_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

            entry_code = """# -*- coding: utf-8 -*-
def run(input_data=None, **kwargs):
    print("【邮件技能】正在抓取收件箱...")
    return {
        "status": "success",
        "emails": [
            {"id": "1", "from": "partner@co.com", "subject": "紧急报价方案确认", "body": "请立即查看最新报价，明天下午需要签署合同。"},
            {"id": "2", "from": "admin@butler.io", "subject": "系统周报摘要", "body": "服务正常运行率 99.9%，CPU 负载在健康水平。"}
        ]
    }
"""
            (email_reader_dir / "main.py").write_text(entry_code, encoding="utf-8")
            self.registry.register("email-reader", "1.1.0", "active")

    def _auto_register_unregistered_packages(self):
        """
        自我修复机制：扫描磁盘文件夹，如果某个包在数据库中未注册登记（例如数据库被清空或重建），自动进行重新注册登记。
        """
        try:
            for p_dir in self.storage_dir.iterdir():
                if p_dir.is_dir():
                    manifest_file = p_dir / "manifest.json"
                    if manifest_file.exists():
                        try:
                            data = json.loads(manifest_file.read_text(encoding="utf-8"))
                            name = data.get("name")
                            version = data.get("version", "1.0.0")
                            if name:
                                status = self.registry.get_package_status(name)
                                if not status:
                                    # 自动注册为激活状态
                                    self.registry.register(name, version, "active")
                        except Exception:
                            pass
        except Exception:
            pass

    def install(self, source_path: str) -> bool:
        """
        安装本地文件目录下的包：复制到存储池，并在 SQLite 中注册登记。
        """
        source = Path(source_path)
        if not source.exists() or not source.is_dir():
            raise FileNotFoundError(f"未找到指定的安装源目录: {source_path}")

        manifest_file = source / "manifest.json"
        if not manifest_file.exists():
            raise ValueError(f"该包缺少 manifest.json 配置文件: {source_path}")

        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            manifest = PackageManifest.from_dict(manifest_data)

            target_dir = self.storage_dir / manifest.name
            if target_dir.exists():
                shutil.rmtree(target_dir)

            shutil.copytree(source, target_dir)
            self.registry.register(manifest.name, manifest.version, "active")
            return True
        except Exception as e:
            print(f"安装包时发生错误: {e}")
            return False

    def uninstall(self, name: str) -> bool:
        """
        卸载物理包：删除其存储文件目录，并同步在 SQLite 中注销登记。
        """
        target_dir = self.storage_dir / name
        if target_dir.exists():
            try:
                shutil.rmtree(target_dir)
            except Exception:
                pass
        return self.registry.unregister(name)

    def get_manifest(self, name: str) -> Optional[PackageManifest]:
        """
        读取并加载包配置。
        """
        manifest_file = self.storage_dir / name / "manifest.json"
        if not manifest_file.exists():
            return None
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            return PackageManifest.from_dict(data)
        except Exception:
            return None

    def execute(self, name: str, input_data: Any = None, **kwargs) -> Any:
        """
        动态热加载并运行指定包的入口脚本及 run 方法。
        """
        manifest = self.get_manifest(name)
        if not manifest:
            raise ValueError(f"未安装指定的包: '{name}'。")

        status = self.registry.get_package_status(name)
        if status != "active":
            raise PermissionError(f"该包被禁用或不处于活动状态: '{name}'。")

        entry_file = self.storage_dir / name / manifest.entry
        if not entry_file.exists():
            raise FileNotFoundError(f"未在包 '{name}' 内找到指定的入口脚本 '{manifest.entry}'。")

        # 动态导入模块
        module_name = f"butler.packages.{name}"
        spec = importlib.util.spec_from_file_location(module_name, str(entry_file))
        if spec is None or spec.loader is None:
            raise ImportError(f"无法生成该文件的动态模块规范: {entry_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # 调用模块中的 run 入口函数
        if not hasattr(module, "run"):
            raise AttributeError(f"模块 '{module_name}' 必须定义 'run(input_data=None, **kwargs)' 接口。")

        return module.run(input_data, **kwargs)
