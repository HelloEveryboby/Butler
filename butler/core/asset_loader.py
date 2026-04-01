import os

class AssetLoader:
    """
    资源加载器，模拟 STM32 内部/外部 Flash 访问逻辑。
    代码逻辑预期在 'Internal Flash'，资源文件在 'External Flash'。
    """
    def __init__(self):
        # 定位项目根目录
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.external_flash_base = os.path.join(self.project_root, "data", "external_flash")
        self.frontend_view_base = os.path.join(self.project_root, "frontend", "view")

    def get_ui_path(self):
        """获取 UI 入口 index.html 的物理路径"""
        return os.path.join(self.frontend_view_base, "index.html")

    def get_web_dir(self):
        """获取 Web 资源根目录"""
        return self.frontend_view_base

    def get_asset_path(self, category, filename):
        """
        获取通用资产路径
        :param category: 类别 (如 'assets', 'audio', 'icons')
        :param filename: 文件名
        """
        return os.path.join(self.external_flash_base, category, filename)

    def resolve_path(self, virtual_path):
        """
        将虚拟路径解析为实际物理路径
        例如: 'ui://index.html' -> '.../frontend/view/index.html'
        """
        if virtual_path.startswith("ui://"):
            return os.path.join(self.frontend_view_base, virtual_path[5:])
        elif virtual_path.startswith("asset://"):
            return os.path.join(self.external_flash_base, "assets", virtual_path[8:])
        elif virtual_path.startswith("audio://"):
            return os.path.join(self.external_flash_base, "audio", virtual_path[8:])
        return virtual_path

# 单例模式供全局使用
asset_loader = AssetLoader()

if __name__ == "__main__":
    loader = AssetLoader()
    print(f"Project Root: {loader.project_root}")
    print(f"UI Path: {loader.get_ui_path()}")
    print(f"Resolved: {loader.resolve_path('asset://settings_icon.png')}")
