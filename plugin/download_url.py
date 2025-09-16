import os
import requests
import logging
from uuid import uuid4
from .abstract_plugin import AbstractPlugin

class DownloadURLPlugin(AbstractPlugin):
    def __init__(self):
        self.temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'temp'))
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def get_name(self) -> str:
        return "download_url"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.logger.info("DownloadURLPlugin initialized.")

    def get_commands(self) -> list[str]:
        return ["download url", "下载网页"]

    def run(self, command: str, args: dict) -> str:
        url = args.get("url")
        if not url:
            return "Error: URL parameter is missing."

        try:
            self.logger.info(f"Downloading content from {url}")
            response = requests.get(url, timeout=15)
            response.raise_for_status()

            # Ensure content is decoded correctly
            content = response.text

            file_name = f"download_{uuid4().hex}.html"
            file_path = os.path.join(self.temp_dir, file_name)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self.logger.info(f"URL content saved to {file_path}")
            return f"Content from the URL has been downloaded and saved to: {file_path}"

        except requests.RequestException as e:
            self.logger.error(f"Failed to download URL {url}: {e}")
            return f"Error: Failed to download content from the URL. {e}"
        except Exception as e:
            self.logger.error(f"An error occurred while processing {url}: {e}")
            return f"Error: An unexpected error occurred. {e}"

    def stop(self):
        pass

    def cleanup(self):
        pass

    def status(self) -> str:
        return "active"
