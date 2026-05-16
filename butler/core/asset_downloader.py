import os
import urllib.request
from pathlib import Path
from butler.core.constants import DATA_DIR
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

# Essential assets mapping
ASSETS_MAPPING = {
    "assets/settings_icon.png": "https://raw.githubusercontent.com/PAYDAY3/Butler/main/data/external_flash/assets/settings_icon.png",
    "audio/activate.wav": "https://raw.githubusercontent.com/PAYDAY3/Butler/main/data/external_flash/audio/activate.wav",
    "audio/jarvis.wav": "https://raw.githubusercontent.com/PAYDAY3/Butler/main/data/external_flash/audio/jarvis.wav"
}

def download_essential_assets():
    """Checks for missing essential assets and downloads them."""
    base_dir = DATA_DIR / "external_flash"

    logger.info("Checking for essential assets...")

    for rel_path, url in ASSETS_MAPPING.items():
        target_path = base_dir / rel_path
        if not target_path.exists():
            try:
                logger.info(f"Downloading missing asset: {rel_path}...")
                target_path.parent.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(url, target_path)
                logger.info(f"Successfully downloaded {rel_path}.")
            except Exception as e:
                logger.error(f"Failed to download asset {rel_path}: {e}")

if __name__ == "__main__":
    download_essential_assets()
