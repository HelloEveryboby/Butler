"""
Data Recycler - A tool to cleanup temporary files generated during project execution.
Supports cleaning __pycache__, .pyc files, build/dist directories, and old logs.
"""
import os
import shutil
import time
import pathlib
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class DataRecycler:
    def __init__(self, root_dir=".", log_retention_days=7):
        self.root_dir = pathlib.Path(root_dir).resolve()
        self.log_retention_days = log_retention_days
        self.temp_dirs = {"temp", "build", "dist", "target"}
        self.temp_patterns = {
            "*.pyc", "*.pyo", "*.pyd", ".DS_Store", "*_last_run.txt",
            "*_exec", "*.so", "*.o", "*.class", "hello_executable"
        }
        self.specific_files = {"scheduled_tasks.log"}
        self.external_dirs = ["/tmp/outputs"]

    def cleanup(self, dry_run=False):
        """
        Executes the cleanup process.
        :param dry_run: If True, only lists the files/dirs to be deleted without actually deleting them.
        :return: A list of deleted items or items to be deleted.
        """
        results = []
        total_size = 0

        # 1. Recursive cleanup using os.walk (topdown=True allows skipping deleted dirs)
        for root, dirs, files in os.walk(self.root_dir, topdown=True):
            # Check for directories to delete
            for d in list(dirs):
                if d == "__pycache__" or d.endswith(".egg-info") or (root == str(self.root_dir) and d in self.temp_dirs):
                    path = pathlib.Path(root) / d
                    try:
                        size = self._get_dir_size(path)
                        results.append(f"[DIR] {path.relative_to(self.root_dir)} ({size} bytes)")
                        total_size += size
                        if not dry_run:
                            shutil.rmtree(path)
                            # Recreate empty temp dir if it's the main temp
                            if d == "temp" and root == str(self.root_dir):
                                os.makedirs(path, exist_ok=True)
                        # Remove from dirs list so os.walk doesn't enter it
                        dirs.remove(d)
                    except Exception as e:
                        logger.error(f"Error processing directory {path}: {e}")

            # Check for files to delete
            for f in files:
                path = pathlib.Path(root) / f
                is_temp_file = False
                for pattern in self.temp_patterns:
                    if path.match(pattern):
                        is_temp_file = True
                        break

                if is_temp_file or (root == str(self.root_dir) and f in self.specific_files):
                    try:
                        size = path.stat().st_size
                        results.append(f"[FILE] {path.relative_to(self.root_dir)} ({size} bytes)")
                        total_size += size
                        if not dry_run:
                            path.unlink()
                    except Exception as e:
                        logger.error(f"Error processing file {path}: {e}")

        # 2. Cleanup old logs
        logs_dir = self.root_dir / "logs"
        if logs_dir.exists() and logs_dir.is_dir():
            now = time.time()
            retention_sec = self.log_retention_days * 24 * 60 * 60
            for log_file in logs_dir.glob("*.log*"):
                try:
                    if log_file.is_file():
                        mtime = log_file.stat().st_mtime
                        if now - mtime > retention_sec:
                            size = log_file.stat().st_size
                            results.append(f"[LOG] {log_file.relative_to(self.root_dir)} ({size} bytes, old)")
                            total_size += size
                            if not dry_run:
                                log_file.unlink()
                except Exception as e:
                    logger.error(f"Error cleaning log file {log_file}: {e}")

        # 3. Cleanup external directories
        for ext_dir in self.external_dirs:
            ext_path = pathlib.Path(ext_dir)
            if ext_path.exists() and ext_path.is_dir():
                try:
                    size = self._get_dir_size(ext_path)
                    results.append(f"[EXT-DIR] {ext_dir} ({size} bytes)")
                    total_size += size
                    if not dry_run:
                        shutil.rmtree(ext_path)
                except Exception as e:
                    logger.error(f"Error cleaning external directory {ext_dir}: {e}")

        summary = f"Cleanup {'(Dry Run) ' if dry_run else ''}finished. Total items: {len(results)}, Total size: {total_size} bytes."
        logger.info(summary)
        return results, summary

    def _get_dir_size(self, path):
        total = 0
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except FileNotFoundError:
                pass
        return total

def run(*args, **kwargs):
    """
    Entry point for Butler ExtensionManager.
    """
    dry_run = kwargs.get('dry_run', False)
    if not dry_run and args:
        # Check if dry_run was passed as a positional arg
        if args[0] in (True, False):
            dry_run = args[0]
        elif isinstance(args[0], str):
            dry_run = args[0].lower() in ("true", "yes", "1", "--dry-run")

    recycler = DataRecycler()

    print(f"Starting Data Recycler (dry_run={dry_run})...")
    items, summary = recycler.cleanup(dry_run=dry_run)

    if not items:
        print("No temporary files found to clean.")
    else:
        for item in items:
            print(item)
    print("-" * 20)
    print(summary)
    return summary

if __name__ == "__main__":
    import sys
    is_dry = "--dry-run" in sys.argv
    run(dry_run=is_dry)
