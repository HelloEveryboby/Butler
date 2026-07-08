import os
import shutil
import json
import logging
from .manifest import ManifestManager

logger = logging.getLogger("AssetSyncHub.Init")

class InitManager:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def init_android(self):
        """Initializes the Android project structure and basic configs."""
        # 1. Create .butler_manifest.json if missing
        mm = ManifestManager(self.root_dir)
        mm.save_default()

        # 2. Create config.template.json if missing
        template_path = os.path.join(self.root_dir, "config.template.json")
        if not os.path.exists(template_path):
            template = {
                "API_HOST": "{{API_HOST}}",
                "VERSION_CODE": "{{VERSION_CODE}}",
                "VERSION_NAME": "{{VERSION_NAME}}",
                "DEBUG_MODE": True
            }
            with open(template_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2)
            logger.info("Created config.template.json")

        # 3. Create android.env example in butler_android if it exists
        android_dir = os.path.join(self.root_dir, "butler_android")
        if os.path.exists(android_dir):
            env_example = os.path.join(android_dir, "android.env.example")
            if not os.path.exists(env_example):
                with open(env_example, 'w', encoding='utf-8') as f:
                    f.write("API_HOST=https://api.prod.com\n")
                    f.write("VERSION_CODE=1\n")
                    f.write("VERSION_NAME=1.0.0\n")
                logger.info("Created android.env.example")

        # 4. Ensure assets/raw exists
        assets_raw = os.path.join(self.root_dir, "assets/textures")
        os.makedirs(assets_raw, exist_ok=True)

        return "Initialization complete."

if __name__ == "__main__":
    im = InitManager(os.getcwd())
    im.init_android()
