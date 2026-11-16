"""butler_dsh — Butler 侧 DSH 插件搬运接入包。

组件：
  client.py        北向客户端（连接器通信）
  plugin_market.py 插件市场下载器 + 安装前体检（分类过滤/白名单/平台检查）
  skill_registry.py 插件能力 → Butler LLM 工具表
  cli.py           butler skill 命令（install/uninstall/list/...）
"""

__version__ = "0.1.0"
