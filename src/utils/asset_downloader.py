import os
import urllib.request
from pathlib import Path
from utils.constants import DATA_DIR
from utils.logger import LogManager
from config.config import config_loader

logger = LogManager.get_logger(__name__)

# Essential assets mapping
ESSENTIAL_ASSETS = [
    "assets/settings_icon.png",
    "audio/activate.wav",
    "audio/butler.wav"
]

def download_essential_assets():
    """Checks for missing essential assets and downloads them."""
    base_dir = DATA_DIR / "external_flash"

    logger.info("Checking for essential assets...")

    base_url = config_loader.get("update_source.assets_base_url", "https://raw.githubusercontent.com/PAYDAY3/Butler/main/data/external_flash/")

    for rel_path in ESSENTIAL_ASSETS:
        url = base_url + rel_path
        target_path = base_dir / rel_path
        if not target_path.exists():
            try:
                logger.info(f"Downloading missing asset from {url}...")
                target_path.parent.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(url, target_path)
                logger.info(f"Successfully downloaded {rel_path}.")
            except Exception as e:
                logger.error(f"Failed to download asset {rel_path}: {e}")

if __name__ == "__main__":
    download_essential_assets()
