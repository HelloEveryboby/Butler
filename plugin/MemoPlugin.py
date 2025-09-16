import os
import json
import logging
from datetime import datetime
from .abstract_plugin import AbstractPlugin

class MemoPlugin(AbstractPlugin):
    def __init__(self):
        self.memo_file = "memos.json"
        self.memos = []

    def get_name(self) -> str:
        return "MemoPlugin"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.load_memos()
        self.logger.info("MemoPlugin initialized.")

    def load_memos(self):
        if os.path.exists(self.memo_file):
            try:
                with open(self.memo_file, 'r', encoding='utf-8') as f:
                    self.memos = json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load memos: {e}")
                self.memos = []

    def save_memos(self):
        try:
            with open(self.memo_file, 'w', encoding='utf-8') as f:
                json.dump(self.memos, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save memos: {e}")

    def get_commands(self) -> list[str]:
        return ["memo", "备忘录"]

    def run(self, command: str, args: dict) -> str:
        action = args.get("action")
        content = args.get("content")
        memo_id = args.get("id")

        if action == "add":
            if not content:
                return "Error: Memo content cannot be empty."
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_id = max([m.get('id', 0) for m in self.memos] + [0]) + 1
            self.memos.append({"id": new_id, "content": content, "timestamp": timestamp, "completed": False})
            self.save_memos()
            return f"Added memo: '{content}'"

        elif action == "list":
            if not self.memos:
                return "You have no memos."
            response = "Your memos:\n"
            for memo in self.memos:
                status = "✓" if memo.get("completed") else " "
                response += f"  {memo['id']}. [{status}] {memo['content']} ({memo['timestamp']})\n"
            return response

        elif action == "complete":
            if not memo_id:
                return "Error: Please provide a memo ID to complete."
            try:
                memo_id = int(memo_id)
                for memo in self.memos:
                    if memo["id"] == memo_id:
                        memo["completed"] = True
                        self.save_memos()
                        return f"Completed memo: '{memo['content']}'"
                return f"Error: Memo with ID {memo_id} not found."
            except (ValueError, TypeError):
                return "Error: Invalid memo ID."

        elif action == "delete":
            if not memo_id:
                return "Error: Please provide a memo ID to delete."
            try:
                memo_id = int(memo_id)
                original_len = len(self.memos)
                self.memos = [m for m in self.memos if m.get("id") != memo_id]
                if len(self.memos) < original_len:
                    self.save_memos()
                    return f"Deleted memo with ID {memo_id}."
                return f"Error: Memo with ID {memo_id} not found."
            except (ValueError, TypeError):
                return "Error: Invalid memo ID."
        
        else:
            return "Usage: memo --action [add|list|complete|delete] --content <text> --id <number>"

    def stop(self):
        pass

    def cleanup(self):
        self.save_memos()
        self.logger.info("MemoPlugin cleaned up and memos saved.")

    def status(self) -> str:
        return f"active - managing {len(self.memos)} memos"
