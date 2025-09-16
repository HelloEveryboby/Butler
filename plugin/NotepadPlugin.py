import os
import json
import logging
from .abstract_plugin import AbstractPlugin

class NotepadPlugin(AbstractPlugin):
    def __init__(self):
        self.notes_file = "notepad.json"
        self.notes = []

    def get_name(self) -> str:
        return "NotepadPlugin"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.load_notes()
        self.logger.info("NotepadPlugin initialized.")

    def load_notes(self):
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, 'r', encoding='utf-8') as f:
                    self.notes = json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load notes: {e}")
                self.notes = []

    def save_notes(self):
        try:
            with open(self.notes_file, 'w', encoding='utf-8') as f:
                json.dump(self.notes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save notes: {e}")

    def get_commands(self) -> list[str]:
        return ["note", "notepad", "笔记"]

    def run(self, command: str, args: dict) -> str:
        action = args.get("action")
        content = args.get("content")
        index = args.get("index")

        if action == "add":
            if not content:
                return "Error: Note content cannot be empty."
            self.notes.append(content)
            self.save_notes()
            return f"Added note: '{content}'"

        elif action == "list":
            if not self.notes:
                return "You have no notes."
            return "Your notes:\n" + "\n".join(f"  {i}: {note}" for i, note in enumerate(self.notes))

        elif action == "delete":
            try:
                index = int(index)
                if 0 <= index < len(self.notes):
                    deleted_note = self.notes.pop(index)
                    self.save_notes()
                    return f"Deleted note: '{deleted_note}'"
                return f"Error: Invalid index {index}."
            except (ValueError, TypeError):
                return "Error: Please provide a valid index to delete."

        elif action == "edit":
            try:
                index = int(index)
                if not content:
                    return "Error: New content for the note cannot be empty."
                if 0 <= index < len(self.notes):
                    self.notes[index] = content
                    self.save_notes()
                    return f"Edited note {index}."
                return f"Error: Invalid index {index}."
            except (ValueError, TypeError):
                return "Error: Please provide a valid index to edit."
        
        else:
            return "Usage: note --action [add|list|delete|edit] --content <text> --index <number>"

    def stop(self):
        pass

    def cleanup(self):
        self.save_notes()
        self.logger.info("NotepadPlugin cleaned up and notes saved.")

    def status(self) -> str:
        return f"active - managing {len(self.notes)} notes"
