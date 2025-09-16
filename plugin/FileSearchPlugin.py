import os
import time
import logging
from .abstract_plugin import AbstractPlugin

class FileSearchPlugin(AbstractPlugin):
    def get_name(self) -> str:
        return "FileSearchPlugin"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.logger.info("FileSearchPlugin initialized.")

    def get_commands(self) -> list[str]:
        return ["search file", "find file", "搜索文件"]

    def run(self, command: str, args: dict) -> str:
        directory = args.get("directory")
        filename = args.get("filename")

        if not directory or not os.path.isdir(directory):
            return f"Error: Invalid directory provided: {directory}"
        if not filename:
            return "Error: No filename provided to search for."

        try:
            self.logger.info(f"Searching for '{filename}' in '{directory}'...")
            matches = []
            start_time = time.time()
            
            for root, dirs, files in os.walk(directory):
                if filename in files:
                    matches.append(os.path.join(root, filename))
                
                # Prevent the search from running for too long
                if time.time() - start_time > 15:
                    self.logger.warning("File search timed out after 15 seconds.")
                    break

            if matches:
                return f"Found file(s) at: {', '.join(matches)}"
            else:
                return f"Could not find a file named '{filename}' in '{directory}'."

        except Exception as e: 
            self.logger.error(f"File search failed: {e}")
            return f"An error occurred during file search: {e}"

    def stop(self):
        pass

    def cleanup(self):
        pass

    def status(self) -> str:
        return "active"
