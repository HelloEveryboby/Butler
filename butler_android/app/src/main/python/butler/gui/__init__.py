"""Butler GUI 模块"""

from butler.gui.config_wizard_enhanced import EnhancedConfigWizard
from butler.gui.config_wizard_enhanced_v2 import ConfigWizardV2
from butler.gui.startup_wizard import StartupWizard, show_startup_wizard_if_needed
import os

def show_config_wizard_if_needed():
    """检查是否需要显示配置向导（V2版）"""
    from butler.core.config_manager import config_manager

    # 检查是否已配置了必需的 API 密钥
    deepseek_key = config_manager.get("api.deepseek_key") or os.getenv("DEEPSEEK_API_KEY", "")

    if not deepseek_key or "YOUR_" in str(deepseek_key):
        print("检测到缺少 API 密钥，显示配置向导 V2")
        wizard = ConfigWizardV2()
        wizard.root.mainloop()
        return True

    return False

__all__ = [
    'EnhancedConfigWizard',
    'ConfigWizardV2',
    'show_config_wizard_if_needed',
    'StartupWizard',
    'show_startup_wizard_if_needed'
]
