import os
import time
import logging
from .abstract_plugin import AbstractPlugin

class WriteFilePlugin(AbstractPlugin):
    def __init__(self):
        self.temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'temp'))
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def get_name(self) -> str:
        return "write_file"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.logger.info("WriteFilePlugin initialized.")

    def get_commands(self) -> list[str]:
        return ["write file", "写入文件"]

    def run(self, command: str, args: dict) -> str:
        content = args.get("content")
        filename = args.get("filename", f"write_file_{int(time.time())}.txt")

        if not content:
            return "Error: No content provided to write."

        file_path = os.path.join(self.temp_dir, filename)

        try:
            self.logger.info(f"Writing content to {file_path}")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Successfully wrote to {file_path}")
            return f"Content has been written to the file: {file_path}"

        except Exception as e:
            self.logger.error(f"Failed to write to file {file_path}: {e}")
            return f"Error: Could not write to file. {e}"

    def stop(self):
        pass

    def cleanup(self):
        pass

    def status(self) -> str:
        return "active"
