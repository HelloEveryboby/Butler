import logging
import chardet
from .abstract_plugin import AbstractPlugin

class ReadFilePlugin(AbstractPlugin):
    def get_name(self) -> str:
        return "read_file"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.logger.info("ReadFilePlugin initialized.")

    def get_commands(self) -> list[str]:
        return ["read file", "读取文件"]

    def run(self, command: str, args: dict) -> str:
        file_path = args.get("file_path")
        if not isinstance(file_path, str) or not file_path.strip():
            return "Error: File path parameter is missing or invalid."

        try:
            self.logger.info(f"Attempting to read file: {file_path}")
            with open(file_path, 'rb') as f:
                raw_content = f.read()

            # Detect encoding and decode
            detected_encoding = chardet.detect(raw_content)['encoding']
            if detected_encoding:
                content = raw_content.decode(detected_encoding)
            else:
                # Fallback to utf-8 if detection fails
                content = raw_content.decode('utf-8', errors='replace')

            self.logger.info(f"Successfully read file: {file_path}")
            return content

        except FileNotFoundError:
            self.logger.error(f"File not found: {file_path}")
            return f"Error: File not found at '{file_path}'."
        except UnicodeDecodeError as e:
            self.logger.error(f"Could not decode file {file_path}: {e}")
            return f"Error: Could not decode file. It might be a binary file or have an unsupported encoding."
        except PermissionError:
            self.logger.error(f"Permission denied to read file: {file_path}")
            return f"Error: Permission denied to read the file at '{file_path}'."
        except Exception as e:
            self.logger.error(f"An error occurred while reading file {file_path}: {e}")
            return f"Error: An unexpected error occurred: {e}"

    def stop(self):
        pass

    def cleanup(self):
        pass

    def status(self) -> str:
        return "active"
