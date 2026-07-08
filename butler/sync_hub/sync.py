import os
import hashlib
import shutil
import json
import logging
import fnmatch
from typing import Dict, List, Any, Set, Optional
from concurrent.futures import ThreadPoolExecutor

from .checker import Checker, CapabilityMatrix
from .manifest import ManifestManager

logger = logging.getLogger("AssetSyncHub.Sync")

class SyncEngine:
    def __init__(self, root_dir: str, checker: Checker, manifest_mgr: ManifestManager):
        self.root_dir = root_dir
        self.checker = checker
        self.manifest_mgr = manifest_mgr
        self.cache_path = os.path.join(root_dir, ".sync_cache.json")
        self.cache = self._load_cache()
        self.matrix = checker.check_env()
        self.force = False

    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"files": {}, "last_sync": None}
        return {"files": {}, "last_sync": None}

    def _save_cache(self):
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2)

    def _get_md5(self, filepath: str) -> str:
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _should_ignore(self, path: str, patterns: List[str]) -> bool:
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
                return True
            # Handle directory patterns
            if pattern.endswith('/') and path.startswith(pattern):
                return True
        return False

    def sync(self, force: bool = False):
        self.force = force
        rules = self.manifest_mgr.get_rules()
        global_ignore = self.manifest_mgr.get_global_ignore()

        stats = {"synced": 0, "skipped": 0, "errors": 0, "conflicts": []}

        for rule in rules:
            self._process_rule(rule, global_ignore, stats)

        self.cache["last_sync"] = hashlib.md5(str(os.times()).encode()).hexdigest() # Dummy timestamp
        self._save_cache()

        # Inject configuration
        self._inject_config(stats)

        # After sync, perform health check (simplified for now)
        self._health_check(stats)
        return stats

    def _inject_config(self, stats: Dict[str, Any]):
        """Injects environment variables into config template and gradle.properties."""
        env_path = os.path.join(self.root_dir, "butler_android", "android.env")
        template_path = os.path.join(self.root_dir, "config.template.json")

        if not os.path.exists(env_path) or not os.path.exists(template_path):
            logger.info("Skipping config injection: android.env or template missing.")
            return

        # Load env
        env = {}
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    env[k.strip()] = v.strip()

        # Load template and replace
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            for k, v in env.items():
                content = content.replace(f"{{{{{k}}}}}", v)

        # Write to Android assets
        dst_config = os.path.join(self.root_dir, "butler_android", "app", "src", "main", "assets", "config.json")
        os.makedirs(os.path.dirname(dst_config), exist_ok=True)
        with open(dst_config, 'w', encoding='utf-8') as f:
            f.write(content)

        # Update gradle.properties
        gradle_props_path = os.path.join(self.root_dir, "butler_android", "gradle.properties")
        if os.path.exists(gradle_props_path):
            lines = []
            with open(gradle_props_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            with open(gradle_props_path, 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.startswith("versionCode=") and "VERSION_CODE" in env:
                        f.write(f"versionCode={env['VERSION_CODE']}\n")
                    elif line.startswith("versionName=") and "VERSION_NAME" in env:
                        f.write(f"versionName={env['VERSION_NAME']}\n")
                    else:
                        f.write(line)

        logger.info("Injected config and updated gradle.properties")

    def _process_rule(self, rule: Dict[str, Any], global_ignore: List[str], stats: Dict[str, Any]):
        src_base = os.path.join(self.root_dir, rule["source"])
        dst_base = os.path.join(self.root_dir, rule["target"])

        if not os.path.exists(src_base):
            logger.warning(f"Source directory {src_base} does not exist. Skipping rule {rule.get('id')}.")
            return

        os.makedirs(dst_base, exist_ok=True)

        rule_exclude = rule.get("exclude", [])
        rule_include = rule.get("include", ["*"])
        rule_filter = rule.get("filter", None) # For assets

        for root, dirs, files in os.walk(src_base):
            # Calculate relative path from src_base
            rel_dir = os.path.relpath(root, src_base)
            if rel_dir == ".":
                rel_dir = ""

            # Filter directories
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.join(rel_dir, d), global_ignore + rule_exclude)]

            for file in files:
                rel_file_path = os.path.join(rel_dir, file)
                if self._should_ignore(rel_file_path, global_ignore + rule_exclude):
                    continue

                # Check if file matches include/filter
                matches = False
                patterns = rule_filter if rule_filter else rule_include
                for pattern in patterns:
                    if fnmatch.fnmatch(file, pattern):
                        matches = True
                        break

                if not matches:
                    continue

                src_file = os.path.join(root, file)
                # Determine destination file name (might change due to conversion)
                dst_file_name = file
                convert_cfg = rule.get("convert")
                if convert_cfg and rule.get("type") == "asset":
                    target_ext = convert_cfg.get("format")
                    if target_ext:
                        dst_file_name = os.path.splitext(file)[0] + "." + target_ext

                dst_file = os.path.join(dst_base, rel_dir, dst_file_name)
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)

                self._sync_file(src_file, dst_file, rule, stats)

    def _sync_file(self, src: str, dst: str, rule: Dict[str, Any], stats: Dict[str, Any]):
        rel_src = os.path.relpath(src, self.root_dir)
        src_md5 = self._get_md5(src)

        # Check cache
        if rel_src in self.cache["files"] and self.cache["files"][rel_src]["md5"] == src_md5:
            if os.path.exists(dst):
                stats["skipped"] += 1
                return

        # Conflict detection for code
        if rule.get("type") == "code" and os.path.exists(dst) and not self.force:
            dst_md5 = self._get_md5(dst)
            # If dst is different from what we last synced, it's a conflict
            last_dst_md5 = self.cache["files"].get(rel_src, {}).get("dst_md5")
            if last_dst_md5 and dst_md5 != last_dst_md5:
                stats["conflicts"].append({"src": src, "dst": dst})
                logger.warning(f"Conflict detected for {rel_src}. Android version has changed.")
                return

        # Perform sync/conversion
        try:
            success = False
            if rule.get("type") == "asset" and rule.get("convert"):
                success = self._convert_asset(src, dst, rule["convert"])

            if not success:
                # Direct copy (fallback or for code)
                shutil.copy2(src, dst)
                success = True

            if success:
                stats["synced"] += 1
                self.cache["files"][rel_src] = {
                    "md5": src_md5,
                    "dst_md5": self._get_md5(dst)
                }
        except Exception as e:
            logger.error(f"Failed to sync {src} to {dst}: {e}")
            stats["errors"] += 1

    def _convert_asset(self, src: str, dst: str, config: Dict[str, Any]) -> bool:
        fmt = config.get("format", "").lower()
        if fmt == "webp" and (self.matrix.has_pillow or self.matrix.has_cwebp):
            return self._convert_to_webp(src, dst, config.get("quality", 80))
        elif fmt == "ogg" and self.matrix.has_ffmpeg:
            return self._convert_to_ogg(src, dst, config.get("sample_rate", 22050))
        return False

    def _convert_to_webp(self, src: str, dst: str, quality: int) -> bool:
        # Try Pillow first
        if self.matrix.has_pillow:
            try:
                from PIL import Image
                with Image.open(src) as img:
                    img.save(dst, "WEBP", quality=quality)
                return True
            except Exception as e:
                logger.debug(f"Pillow conversion failed for {src}: {e}")

        # Try cwebp
        cwebp_path = self.checker.get_tool_path("cwebp")
        if cwebp_path:
            try:
                subprocess.run([cwebp_path, "-q", str(quality), src, "-o", dst],
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True
            except Exception as e:
                logger.debug(f"cwebp conversion failed for {src}: {e}")

        return False

    def _convert_to_ogg(self, src: str, dst: str, sample_rate: int) -> bool:
        ffmpeg_path = self.checker.get_tool_path("ffmpeg")
        if ffmpeg_path:
            try:
                subprocess.run([ffmpeg_path, "-i", src, "-ar", str(sample_rate), "-acodec", "libvorbis", dst, "-y"],
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return True
            except Exception as e:
                logger.debug(f"ffmpeg conversion failed for {src}: {e}")
        return False

    def _health_check(self, stats: Dict[str, Any]):
        # Check bundle size
        total_size = 0
        android_assets = os.path.join(self.root_dir, "butler_android/app/src/main/assets")
        if os.path.exists(android_assets):
            for root, _, files in os.walk(android_assets):
                for f in files:
                    total_size += os.path.getsize(os.path.join(root, f))

        stats["bundle_size_mb"] = total_size / (1024 * 1024)
        if stats["bundle_size_mb"] > 150:
            logger.warning(f"Bundle size alert: {stats['bundle_size_mb']:.2f} MB exceeds 150MB threshold.")

        # Generate .asset_meta (simplified)
        meta = {
            "version": "1.0.0",
            "files": {rel: data["md5"] for rel, data in self.cache["files"].items()},
            "total_size": total_size
        }
        meta_path = os.path.join(android_assets, ".asset_meta")
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)

if __name__ == "__main__":
    # Test
    c = Checker(os.getcwd())
    m = ManifestManager(os.getcwd())
    m.load()
    engine = SyncEngine(os.getcwd(), c, m)
    # Caution: running this will actually copy files if directories exist
    # result = engine.sync()
    # print(f"Sync result: {result}")
