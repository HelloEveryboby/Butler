import json
import os
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("AssetSyncHub.Manifest")

DEFAULT_MANIFEST = {
    "version": "1.0",
    "sync_rules": [
        {
            "id": "core_code",
            "source": "butler/",
            "target": "butler_android/app/src/main/python/butler/",
            "include": ["*.py", "*.json", "*.yaml", "*.md"],
            "exclude": ["**/__pycache__/**", "gui/config_wizard*", "gui/startup_wizard*"],
            "type": "code"
        },
        {
            "id": "package_code",
            "source": "package/",
            "target": "butler_android/app/src/main/python/package/",
            "include": ["*.py", "*.md"],
            "exclude": ["**/__pycache__/**"],
            "type": "code"
        },
        {
            "id": "skills_code",
            "source": "skills/",
            "target": "butler_android/app/src/main/python/skills/",
            "include": ["*.py", "*.md", "*.json", "*.yaml"],
            "exclude": ["**/__pycache__/**"],
            "type": "code"
        },
        {
            "id": "programs_code",
            "source": "programs/",
            "target": "butler_android/app/src/main/python/programs/",
            "include": ["*"],
            "exclude": ["**/node_modules/**", "**/target/**", "**/bin/**", "**/obj/**"],
            "type": "code"
        },
        {
            "id": "assets_textures",
            "source": "assets/textures/",
            "target": "butler_android/app/src/main/assets/textures/",
            "filter": ["*.png", "*.jpg", "*.jpeg"],
            "convert": {
                "format": "webp",
                "quality": 80
            },
            "type": "asset"
        },
        {
            "id": "assets_audio",
            "source": "assets/audio/",
            "target": "butler_android/app/src/main/assets/audio/",
            "filter": ["*.wav", "*.mp3"],
            "convert": {
                "format": "ogg",
                "sample_rate": 22050
            },
            "type": "asset"
        },
        {
            "id": "frontend_web",
            "source": "frontend/",
            "target": "butler_android/app/src/main/assets/www/",
            "include": ["*.html", "*.css", "*.js", "*.png", "*.svg", "*.json", "src/**/*.js", "src/**/*.css"],
            "exclude": ["node_modules/**"],
            "type": "asset"
        }
    ],
    "ignore": [".git/*", ".sync_cache.json", ".sync_backups/*", "venv/*", "lib_external/*"]
}

class ManifestManager:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.manifest_path = os.path.join(root_dir, ".butler_manifest.json")
        self.data = {}

    def load(self) -> Dict[str, Any]:
        """Loads manifest from file or returns default if missing."""
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                    self.data = self._merge_with_defaults(user_data)
                    logger.info("Loaded user manifest from .butler_manifest.json")
            except Exception as e:
                logger.error(f"Failed to load manifest: {e}. Using defaults.")
                self.data = DEFAULT_MANIFEST
        else:
            self.data = DEFAULT_MANIFEST
            logger.info("No manifest found. Using default rules.")

        return self.data

    def save_default(self):
        """Saves the default manifest to .butler_manifest.json if it doesn't exist."""
        if not os.path.exists(self.manifest_path):
            with open(self.manifest_path, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_MANIFEST, f, indent=2, ensure_ascii=False)
            logger.info(f"Created default manifest at {self.manifest_path}")

    def _merge_with_defaults(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merges user manifest with defaults."""
        # Simplified merge: user rules can add to or replace default rules by ID
        merged = DEFAULT_MANIFEST.copy()

        if "sync_rules" in user_data:
            user_rules = user_data["sync_rules"]
            default_rules = {rule["id"]: rule for rule in merged["sync_rules"] if "id" in rule}

            for u_rule in user_rules:
                if "id" in u_rule and u_rule["id"] in default_rules:
                    # Update existing rule
                    default_rules[u_rule["id"]].update(u_rule)
                else:
                    # Add new rule
                    merged["sync_rules"].append(u_rule)

        if "ignore" in user_data:
            merged["ignore"] = list(set(merged["ignore"] + user_data["ignore"]))

        return merged

    def get_rules(self) -> List[Dict[str, Any]]:
        return self.data.get("sync_rules", [])

    def get_global_ignore(self) -> List[str]:
        return self.data.get("ignore", [])

if __name__ == "__main__":
    # Test
    manager = ManifestManager(os.getcwd())
    data = manager.load()
    print(f"Loaded {len(data['sync_rules'])} sync rules.")
    for rule in data['sync_rules']:
        print(f"Rule: {rule.get('id')} -> {rule.get('source')} to {rule.get('target')}")
