import os
import shutil
import subprocess
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("AssetSyncHub.Checker")

class CapabilityMatrix:
    def __init__(self):
        self.has_cwebp = False
        self.has_ffmpeg = False
        self.has_pillow = False
        self.mode = "Compatibility"  # Compatibility, Full, or Restricted

    def __repr__(self):
        return f"<CapabilityMatrix mode={self.mode} cwebp={self.has_cwebp} ffmpeg={self.has_ffmpeg} pillow={self.has_pillow}>"

class Checker:
    # Protected paths in Android project that should never be touched by sync
    FORBIDDEN_PATHS = [
        "app/src/main/java/",
        "app/src/main/kotlin/",
        "app/src/main/res/values/strings.xml",
        "app/build.gradle",
        "app/src/main/AndroidManifest.xml",
        "app/src/main/res/mipmap-",
        "gradle/",
        "build.gradle.kts",
        "settings.gradle.kts",
        "gradlew",
        "gradlew.bat"
    ]

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.tools_dir = os.path.join(root_dir, "butler", "tools")
        self.matrix = CapabilityMatrix()

    def check_env(self) -> CapabilityMatrix:
        """Checks for required tools and libraries."""
        # 1. Check for Pillow
        try:
            from PIL import Image
            self.matrix.has_pillow = True
        except ImportError:
            self.matrix.has_pillow = False

        # 2. Check for cwebp
        self.matrix.has_cwebp = self._check_tool("cwebp")

        # 3. Check for ffmpeg
        self.matrix.has_ffmpeg = self._check_tool("ffmpeg")

        # Determine mode
        if self.matrix.has_cwebp and self.matrix.has_ffmpeg:
            self.matrix.mode = "Full"
        elif self.matrix.has_pillow or self.matrix.has_cwebp:
            self.matrix.mode = "Compatibility"
        else:
            self.matrix.mode = "Restricted"

        return self.matrix

    def _check_tool(self, tool_name: str) -> bool:
        """Check if a tool is available in PATH or butler/tools."""
        # Check system PATH
        if shutil.which(tool_name):
            return True

        # Check butler/tools
        ext = ".exe" if os.name == "nt" else ""
        local_tool = os.path.join(self.tools_dir, f"{tool_name}{ext}")
        if os.path.exists(local_tool):
            # Optionally add to PATH for current process
            # os.environ["PATH"] += os.pathsep + self.tools_dir
            return True

        return False

    def is_path_forbidden(self, relative_path: str) -> bool:
        """Checks if a path (relative to butler_android) is in the forbidden list."""
        relative_path = relative_path.replace("\\", "/")
        for forbidden in self.FORBIDDEN_PATHS:
            if relative_path.startswith(forbidden):
                return True
        return False

    def get_tool_path(self, tool_name: str) -> Optional[str]:
        """Returns the absolute path to a tool if found."""
        system_path = shutil.which(tool_name)
        if system_path:
            return system_path

        ext = ".exe" if os.name == "nt" else ""
        local_tool = os.path.join(self.tools_dir, f"{tool_name}{ext}")
        if os.path.exists(local_tool):
            return local_tool

        return None

if __name__ == "__main__":
    # Basic self-test
    checker = Checker(os.getcwd())
    matrix = checker.check_env()
    print(f"Environment check result: {matrix}")

    test_path = "app/src/main/java/com/butler/MainActivity.kt"
    print(f"Is '{test_path}' forbidden? {checker.is_path_forbidden(test_path)}")

    test_path_assets = "app/src/main/assets/ui/logo.png"
    print(f"Is '{test_path_assets}' forbidden? {checker.is_path_forbidden(test_path_assets)}")
