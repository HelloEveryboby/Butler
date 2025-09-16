import os
import pickle
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .abstract_plugin import AbstractPlugin

class FileIndexer:
    def __init__(self, logger):
        self.logger = logger
        self.index = {}  # {filename_lower: [full_path1, full_path2]}
        self.cache_path = os.path.expanduser("~/.butler_file_index.pkl")
        self.observer = None
        self.watch_dirs = set()
    
    def build_index(self, root_paths):
        self.logger.info("Building file index...")
        start_time = time.time()
        
        for root_path in root_paths:
            if not os.path.isdir(root_path):
                continue
            for dirpath, _, filenames in os.walk(root_path, followlinks=False):
                for fname in filenames:
                    try:
                        full_path = os.path.join(dirpath, fname)
                        key = fname.lower()
                        self.index.setdefault(key, []).append(full_path)
                    except Exception as e:
                        self.logger.warning(f"Could not process file {fname} in {dirpath}: {e}")
        
        self.logger.info(f"Index built in {time.time()-start_time:.2f}s. Indexed {sum(len(v) for v in self.index.values())} files.")
    
    def save_index(self):
        with open(self.cache_path, 'wb') as f:
            pickle.dump(self.index, f)
    
    def load_index(self):
        if os.path.exists(self.cache_path):
            with open(self.cache_path, 'rb') as f:
                self.index = pickle.load(f)
            return True
        return False
    
    def start_monitoring(self, paths):
        self.observer = Observer()
        handler = IndexUpdateHandler(self)
        
        for path in paths:
            if os.path.isdir(path):
                self.watch_dirs.add(path)
                self.observer.schedule(handler, path, recursive=True)
        
        if self.watch_dirs:
            self.observer.start()
    
    def stop_monitoring(self):
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

class IndexUpdateHandler(FileSystemEventHandler):
    def __init__(self, indexer):
        self.indexer = indexer
    
    def on_created(self, event):
        if not event.is_directory:
            self._add_to_index(event.src_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            self._remove_from_index(event.src_path)
    
    def on_moved(self, event):
        if not event.is_directory:
            self._remove_from_index(event.src_path)
            self._add_to_index(event.dest_path)
    
    def _add_to_index(self, path):
        fname = os.path.basename(path).lower()
        self.indexer.index.setdefault(fname, []).append(path)
    
    def _remove_from_index(self, path):
        fname = os.path.basename(path).lower()
        if fname in self.indexer.index:
            self.indexer.index[fname] = [p for p in self.indexer.index[fname] if p != path]
            if not self.indexer.index[fname]:
                del self.indexer.index[fname]

class GlobalFileSearchPlugin(AbstractPlugin):
    def __init__(self):
        self.max_results = 50
        self.indexer = None
        # WARNING: Searching the entire filesystem can be very slow and resource-intensive.
        self.root_paths = self._get_root_paths()

    def _get_root_paths(self):
        """Gets the root paths of the system drives."""
        if os.name == 'posix':
            return ["/"]
        else: # Assumes Windows
            return [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:")]
    
    def get_name(self) -> str:
        return "GlobalFileSearchPlugin"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.indexer = FileIndexer(logger)
        
        if not self.indexer.load_index():
            self.indexer.build_index(self.root_paths)
            self.indexer.save_index()
        
        self.indexer.start_monitoring(self.root_paths)
        self.logger.info("GlobalFileSearchPlugin initialized.")
    
    def get_commands(self) -> list[str]:
        return ["global search", "全局搜索"]

    def run(self, command: str, args: dict) -> str:
        pattern = args.get("pattern")
        if not pattern:
            return "Error: Please provide a filename or keyword to search for."
        
        try:
            pattern = pattern.lower()
            results = []

            # Exact match first
            if pattern in self.indexer.index:
                results.extend(self.indexer.index[pattern])

            # Substring match
            for fname, paths in self.indexer.index.items():
                if pattern in fname and fname != pattern:
                    results.extend(paths)
                    if len(results) >= self.max_results:
                        break

            if not results:
                return "No matching files found."

            result_str = f"Found {len(results)} results:\n"
            result_str += "\n".join(results[:self.max_results])

            if len(results) > self.max_results:
                result_str += f"\n(Showing first {self.max_results} results)"

            return result_str
        except Exception as e:
            self.logger.error(f"Global file search failed: {e}")
            return f"An error occurred during search: {e}"

    def stop(self):
        if self.indexer:
            self.indexer.stop_monitoring()

    def cleanup(self):
        if self.indexer:
            self.indexer.stop_monitoring()
            self.indexer.save_index()
            self.logger.info("GlobalFileSearchPlugin cleaned up and index saved.")

    def status(self) -> str:
        if self.indexer and self.indexer.observer and self.indexer.observer.is_alive():
            return f"active - indexing {sum(len(v) for v in self.indexer.index.values())} files"
        return "inactive"
