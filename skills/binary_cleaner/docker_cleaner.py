"""
Docker 孤立资源清理模块。
清理 dangling images、unused volumes、stopped containers、build cache。
"""

import json
import shutil
import logging
import subprocess

logger = logging.getLogger(__name__)


class DockerCleaner:
    """Docker 孤立资源清理器"""

    def __init__(self):
        self.docker_bin = shutil.which("docker")

    def is_available(self) -> bool:
        """Docker 是否可用"""
        if not self.docker_bin:
            return False
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def scan(self) -> dict:
        """扫描 Docker 孤立资源"""
        if not self.is_available():
            return {"available": False, "error": "Docker 不可用"}

        result = {
            "available": True,
            "dangling_images": self._scan_dangling_images(),
            "stopped_containers": self._scan_stopped_containers(),
            "unused_volumes": self._scan_unused_volumes(),
            "build_cache": self._scan_build_cache(),
        }

        total_size = (
            result["dangling_images"]["size_bytes"]
            + result["build_cache"]["size_bytes"]
            + sum(v.get("size_bytes", 0) for v in result["unused_volumes"].get("items", []))
        )
        result["total_size_bytes"] = total_size
        result["total_size_gb"] = round(total_size / (1024 ** 3), 2)
        return result

    def clean(self, dry_run: bool = True) -> dict:
        """清理 Docker 孤立资源"""
        if not self.is_available():
            return {"available": False}

        results = {}

        # dangling images
        cmd = ["docker", "image", "prune", "-f"]
        if dry_run:
            cmd = ["docker", "image", "prune", "--dry-run", "-f"]
        results["images"] = self._run_cmd(cmd)

        # stopped containers
        stopped = self._scan_stopped_containers()
        if stopped.get("items"):
            for container in stopped["items"]:
                cid = container.get("id", "")
                if dry_run:
                    logger.info(f"  [dry-run] 将删除容器: {cid}")
                else:
                    self._run_cmd(["docker", "rm", cid])

        # unused volumes
        cmd = ["docker", "volume", "prune", "-f"]
        if dry_run:
            cmd = ["docker", "volume", "prune", "--dry-run", "-f"]
        results["volumes"] = self._run_cmd(cmd)

        # build cache
        cmd = ["docker", "builder", "prune", "-f"]
        if dry_run:
            cmd = ["docker", "builder", "prune", "--dry-run", "-f"]
        results["build_cache"] = self._run_cmd(cmd)

        return {"dry_run": dry_run, "results": results}

    def _scan_dangling_images(self) -> dict:
        try:
            result = subprocess.run(
                ["docker", "images", "-f", "dangling=true", "--format",
                 "{{.ID}}\t{{.Size}}\t{{.CreatedSince}}"],
                capture_output=True, text=True, timeout=15,
            )
            items = []
            total_size = 0
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t")
                items.append({
                    "id": parts[0] if len(parts) > 0 else "",
                    "size": parts[1] if len(parts) > 1 else "",
                    "created": parts[2] if len(parts) > 2 else "",
                })
            return {"count": len(items), "items": items, "size_bytes": total_size}
        except Exception as e:
            return {"count": 0, "items": [], "size_bytes": 0, "error": str(e)}

    def _scan_stopped_containers(self) -> dict:
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "-f", "status=exited", "--format",
                 "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Size}}"],
                capture_output=True, text=True, timeout=15,
            )
            items = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t")
                items.append({
                    "id": parts[0] if len(parts) > 0 else "",
                    "name": parts[1] if len(parts) > 1 else "",
                    "status": parts[2] if len(parts) > 2 else "",
                    "size": parts[3] if len(parts) > 3 else "",
                })
            return {"count": len(items), "items": items}
        except Exception as e:
            return {"count": 0, "items": [], "error": str(e)}

    def _scan_unused_volumes(self) -> dict:
        try:
            result = subprocess.run(
                ["docker", "volume", "ls", "-f", "dangling=true", "--format",
                 "{{.Name}}\t{{.Driver}}"],
                capture_output=True, text=True, timeout=15,
            )
            items = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t")
                items.append({
                    "name": parts[0] if len(parts) > 0 else "",
                    "driver": parts[1] if len(parts) > 1 else "",
                })
            return {"count": len(items), "items": items}
        except Exception as e:
            return {"count": 0, "items": [], "error": str(e)}

    def _scan_build_cache(self) -> dict:
        try:
            result = subprocess.run(
                ["docker", "builder", "du", "--format", "{{json .}}"],
                capture_output=True, text=True, timeout=15,
            )
            total_size = 0
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    # 不同版本格式不同，尝试多种字段
                    total_size += data.get("size", 0) or data.get("Size", 0) or 0
                except json.JSONDecodeError:
                    pass
            return {"size_bytes": total_size}
        except Exception:
            return {"size_bytes": 0}

    def _run_cmd(self, cmd: list[str]) -> dict:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() if result.returncode != 0 else "",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
