import os
import shutil
from typing import List, Tuple, Dict
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class SmartMigrationEngine:
    """
    Handles logical data migration based on environment logic segments.
    Moves files from temporary/external storage to 'Higher/Core' level.
    """
    def __init__(self, core_root: str = "data/core_system"):
        self.core_root = core_root
        self.logic_segments = {
            "CORE_LOGIC": "logic_segments",
            "MEDIA_ASSETS": "media",
            "SYSTEM_SOUNDS": "assets/sounds",
            "USER_DATA": "data/user_data"
        }
        self._ensure_dirs()

    def _ensure_dirs(self):
        for path in self.logic_segments.values():
            os.makedirs(os.path.join(self.core_root, path), exist_ok=True)

    def migrate_file(self, source_file: str, segment: str) -> Tuple[bool, str]:
        """
        Migrates a single file into a core logic segment.
        """
        if not os.path.exists(source_file):
            return False, f"源文件 '{source_file}' 不存在。"

        target_subfolder = self.logic_segments.get(segment)
        if not target_subfolder:
            return False, f"无效的逻辑段: {segment}。"

        target_dir = os.path.join(self.core_root, target_subfolder)
        filename = os.path.basename(source_file)
        target_path = os.path.join(target_dir, filename)

        try:
            # Atomic move if possible, or copy then delete
            shutil.copy2(source_file, target_path)
            os.remove(source_file)
            logger.info(f"Successfully migrated {filename} to {segment} ({target_path})")
            return True, f"文件 '{filename}' 已成功迁移至核心级别 ({segment})。"
        except Exception as e:
            logger.error(f"Migration error for {source_file}: {e}")
            return False, f"迁移失败: {e}"

    def auto_classify_and_migrate(self, source_dir: str) -> List[Tuple[str, bool, str]]:
        """
        Automatically classifies and migrates files from a directory.
        """
        results = []
        if not os.path.isdir(source_dir):
            return [("Source is not a directory", False, "ERROR")]

        for filename in os.listdir(source_dir):
            source_path = os.path.join(source_dir, filename)
            if os.path.isdir(source_path): continue

            # Classification logic based on "Higher/Core Level" rules
            segment = "USER_DATA"
            if filename.endswith(".py"): segment = "CORE_LOGIC"
            elif filename.endswith((".wav", ".mp3")): segment = "SYSTEM_SOUNDS"
            elif filename.endswith((".jpg", ".png", ".webp")): segment = "MEDIA_ASSETS"

            success, msg = self.migrate_file(source_path, segment)
            results.append((filename, success, segment))

        return results

if __name__ == "__main__":
    # Quick test
    engine = SmartMigrationEngine("temp_core")
    with open("test_logic.py", "w") as f: f.write("# Test logic")
    success, msg = engine.migrate_file("test_logic.py", "CORE_LOGIC")
    print(f"Migration status: {success}, {msg}")
    if os.path.exists("temp_core"): shutil.rmtree("temp_core")
