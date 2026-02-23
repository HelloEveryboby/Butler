import os
import time
import json
from package.core_utils.log_manager import LogManager
from plugin.plugin_interface import AbstractPlugin, PluginResult

logging = LogManager.get_logger(__name__)

class NotepadPlugin(AbstractPlugin):
    def __init__(self):
        self.name = "NotepadPlugin"
        self.chinese_name = "记事本"
        self.description = "记录简单的文本笔记"
        self.parameters = {"note": "str", "action": "str", "index": "int"}
        self.notes = []

    def valid(self) -> bool:
        return True

    def init(self, logging):
        self.logger = LogManager.get_logger(self.name)
        self.load_notes()  # 加载笔记

    def get_name(self):
        return self.name

    def get_chinese_name(self):
        return self.chinese_name

    def get_description(self):
        return self.description

    def get_parameters(self):
        return self.parameters

    def on_startup(self):
        self.logger.info("记事本插件启动")

    def on_shutdown(self):
        self.logger.info("记事本插件关闭。")
        self.save_notes()  # 保存笔记

    def on_pause(self):
        self.logger.info("记事本插件暂停。")

    def on_resume(self):
        self.logger.info("记事本插件恢复。")

    def get_commands(self) -> list[str]:
        return ["记笔记", "添加笔记", "查看笔记", "删除笔记", "编辑笔记", "搜索笔记"]

    def run(self, takecommand: str, args: dict) -> PluginResult:
        action = args.get("action")
        note = args.get("note")
        index = args.get("index")

        if "add" in takecommand or "添加" in takecommand:
            return self.add_note(note)
        elif "view" in takecommand or "查看" in takecommand:
            return self.view_notes()
        elif "delete" in takecommand or "删除" in takecommand:
            return self.delete_note(index)
        elif "edit" in takecommand or "编辑" in takecommand:
            return self.edit_note(index, note)
        elif "search" in takecommand or "搜索" in takecommand:
            return self.search_notes(note)
        else:
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="无效的操作")

    def add_note(self, note: str) -> PluginResult:
        if not note:
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="缺少笔记参数")
        
        self.notes.append(note)
        return PluginResult.new(result="笔记添加成功", need_call_brain=False, success=True)

    def view_notes(self) -> PluginResult:
        if not self.notes:
            return PluginResult.new(result="没有可用的笔记", need_call_brain=False, success=True)
        return PluginResult.new(result="\n".join(f"{i}: {note}" for i, note in enumerate(self.notes)), need_call_brain=False, success=True)

    def delete_note(self, index: int) -> PluginResult:
        if index is None or index < 0 or index >= len(self.notes):
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="无效的索引")
        
        deleted_note = self.notes.pop(index)
        return PluginResult.new(result=f"笔记 '{deleted_note}' 删除成功", need_call_brain=False, success=True)

    def edit_note(self, index: int, new_note: str) -> PluginResult:
        if index is None or index < 0 or index >= len(self.notes):
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="无效的索引")
        
        if not new_note:
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="缺少新笔记内容")
        
        self.notes[index] = new_note
        return PluginResult.new(result="笔记编辑成功", need_call_brain=False, success=True)

    def search_notes(self, keyword: str) -> PluginResult:
        if not keyword:
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="缺少搜索关键字")
        
        found_notes = [note for note in self.notes if keyword in note]
        if not found_notes:
            return PluginResult.new(result="没有找到匹配的笔记", need_call_brain=False, success=True)
        return PluginResult.new(result="\n".join(found_notes), need_call_brain=False, success=True)

    def save_notes(self):
        with open("notes.json", "w") as f:
            json.dump(self.notes, f)  # 保存笔记到文件

    def load_notes(self):
        if os.path.exists("notes.json"):
            with open("notes.json", "r") as f:
                self.notes = json.load(f)  # 从文件加载笔记
