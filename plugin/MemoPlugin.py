import os
import json
from datetime import datetime
from .abstract_plugin import AbstractPlugin, PluginResult

class MemoPlugin(AbstractPlugin):
    def __init__(self):
        super().__init__()
        self.memo_file = "memos.json"
        self.memos = []
        self.load_memos()

    def valid(self) -> bool:
        return True  # 此插件总是可用

    def init(self, logger):
        self.logger = logger
        self.logger.info("MemoPlugin 初始化完成")

    def get_name(self) -> str:
        return "MemoPlugin"

    def load_memos(self):
        """从文件加载备忘录"""
        if os.path.exists(self.memo_file):
            try:
                with open(self.memo_file, 'r', encoding='utf-8') as f:
                    self.memos = json.load(f)
            except Exception as e:
                self.logger.error(f"加载备忘录失败: {e}")
                self.memos = []

    def save_memos(self):
        """保存备忘录到文件"""
        try:
            with open(self.memo_file, 'w', encoding='utf-8') as f:
                json.dump(self.memos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存备忘录失败: {e}")

    def add_memo(self, content: str):
        """添加新备忘录"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.memos.append({
            "id": len(self.memos) + 1,
            "content": content,
            "timestamp": timestamp,
            "completed": False
        })
        self.save_memos()
        return f"已添加备忘录: {content}"

    def list_memos(self, show_all=False):
        """列出备忘录"""
        if not self.memos:
            return "当前没有备忘录"
        
        result = "备忘录列表:\n"
        for memo in self.memos:
            if show_all or not memo["completed"]:
                status = "✓" if memo["completed"] else " "
                result += f"{memo['id']}. [{status}] {memo['content']} ({memo['timestamp']})\n"
        return result

    def complete_memo(self, memo_id: int):
        """标记备忘录为完成"""
        for memo in self.memos:
            if memo["id"] == memo_id:
                memo["completed"] = True
                self.save_memos()
                return f"已将备忘录标记为完成: {memo['content']}"
        return f"未找到ID为 {memo_id} 的备忘录"

    def delete_memo(self, memo_id: int):
        """删除备忘录"""
        for i, memo in enumerate(self.memos):
            if memo["id"] == memo_id:
                content = memo["content"]
                del self.memos[i]
                self.save_memos()
                return f"已删除备忘录: {content}"
        return f"未找到ID为 {memo_id} 的备忘录"

    def run(self, command: str, args: dict) -> PluginResult:
        original_command = args.get('original_command', '')
        
        if "添加备忘录" in original_command:
            content = original_command.replace("添加备忘录", "").strip()
            if content:
                result = self.add_memo(content)
                return PluginResult(success=True, result=result)
            return PluginResult(success=False, error_message="备忘录内容不能为空")
        
        elif "列出备忘录" in original_command:
            show_all = "所有" in original_command
            result = self.list_memos(show_all)
            return PluginResult(success=True, result=result)
        
        elif "完成备忘录" in original_command:
            try:
                memo_id = int(original_command.replace("完成备忘录", "").strip())
                result = self.complete_memo(memo_id)
                return PluginResult(success=True, result=result)
            except ValueError:
                return PluginResult(success=False, error_message="请输入有效的备忘录ID")
        
        elif "删除备忘录" in original_command:
            try:
                memo_id = int(original_command.replace("删除备忘录", "").strip())
                result = self.delete_memo(memo_id)
                return PluginResult(success=True, result=result)
            except ValueError:
                return PluginResult(success=False, error_message="请输入有效的备忘录ID")
        
        return PluginResult(
            success=False,
            error_message="无法识别的备忘录命令，请使用添加备忘录/列出备忘录/完成备忘录/删除备忘录"
        )

    def stop(self):
        return PluginResult(success=True, result="备忘录插件已停止")

    def status(self):
        return PluginResult(success=True, result=f"已保存 {len(self.memos)} 条备忘录")

    def cleanup(self):
        self.save_memos()
