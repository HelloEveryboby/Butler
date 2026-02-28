# pip install watchdog
import os
import pickle
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .plugin_interface import AbstractPlugin, PluginResult

class FileIndexer:
    def __init__(self, logger):
        self.logger = logger
        self.index = {}  # {filename_lower: [full_path1, full_path2]}
        self.cache_path = os.path.expanduser("~/.file_index_cache")
        self.observer = None
        self.watch_dirs = set()
    
    def build_index(self, root_paths):
        """构建初始文件索引"""
        self.logger.info("开始构建文件索引...")
        start_time = time.time()
        
        for root_path in root_paths:
            for dirpath, _, filenames in os.walk(root_path):
                for fname in filenames:
                    full_path = os.path.join(dirpath, fname)
                    key = fname.lower()
                    self.index.setdefault(key, []).append(full_path)
        
        self.logger.info(f"索引构建完成! 耗时 {time.time()-start_time:.2f}秒, 索引文件数: {sum(len(v) for v in self.index.values())}")
    
    def save_index(self):
        """保存索引到文件"""
        with open(self.cache_path, 'wb') as f:
            pickle.dump(self.index, f)
    
    def load_index(self):
        """从文件加载索引"""
        if os.path.exists(self.cache_path):
            with open(self.cache_path, 'rb') as f:
                self.index = pickle.load(f)
            return True
        return False
    
    def start_monitoring(self, paths):
        """启动文件系统监控"""
        self.observer = Observer()
        handler = IndexUpdateHandler(self)
        
        for path in paths:
            if os.path.exists(path):
                self.watch_dirs.add(path)
                self.observer.schedule(handler, path, recursive=True)
        
        self.observer.start()
    
    def stop_monitoring(self):
        if self.observer:
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
            new_list = [p for p in self.indexer.index[fname] if p != path]
            if new_list:
                self.indexer.index[fname] = new_list
            else:
                del self.indexer.index[fname]

class GlobalFileSearchPlugin(AbstractPlugin):
    def __init__(self):
        super().__init__()
        self.max_results = 50
        self.indexer = None
        self.root_paths = self._get_root_paths()

    def get_name(self) -> str:
        return "GlobalFileSearchPlugin"

    def get_chinese_name(self) -> str:
        return "全局文件搜索插件"

    def get_description(self) -> str:
        return "在整个系统范围内构建索引并快速搜索文件"

    def get_parameters(self) -> dict:
        return {
            "pattern": "搜索关键词"
        }

    def on_startup(self):
        self.logger.info("GlobalFileSearchPlugin 已启动")

    def on_shutdown(self):
        self.logger.info("GlobalFileSearchPlugin 已关闭")

    def valid(self) -> bool:
        try:
            import watchdog
            return True
        except ImportError:
            return False

    def _get_root_paths(self):
        """获取系统根路径"""
        if os.name == 'posix':
            # Avoid scanning root in restricted environments, use current dir
            return ["."]
        else:
            return [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:")]
    
    def init(self, logger):
        self.logger = logger
        self.indexer = FileIndexer(logger)
        
        # 尝试加载缓存
        if not self.indexer.load_index():
            self.indexer.build_index(self.root_paths)
            self.indexer.save_index()
        
        # 启动文件监控
        self.indexer.start_monitoring(self.root_paths)
        logger.info("文件索引服务已启动")
    
    def search_files(self, pattern: str):
        pattern = pattern.lower()
        results = []
        
        # 精确匹配优先
        if pattern in self.indexer.index:
            results.extend(self.indexer.index[pattern])
        
        # 模糊匹配
        for fname, paths in self.indexer.index.items():
            if pattern in fname and fname != pattern:
                results.extend(paths)
                if len(results) >= self.max_results:
                    break
        
        # 结果处理
        if not results:
            return "未找到匹配的文件"
        
        result_str = f"找到 {len(results)} 个结果:\n"
        for i, path in enumerate(results[:self.max_results], 1):
            result_str += f"{i}. {path}\n"
        
        if len(results) > self.max_results:
            result_str += f"\n(仅显示前 {self.max_results} 个结果)"
        
        return result_str

    def get_commands(self) -> list[str]:
        return ["搜索文件"]

    def run(self, command: str, args: dict) -> PluginResult:
        pattern = args.get("pattern")
        if not pattern:
            return PluginResult.new(
                success=False,
                error_message="请输入要搜索的文件名关键词"
            )
        
        try:
            result = self.search_files(pattern)
            return PluginResult.new(success=True, result=result)
        except Exception as e:
            return PluginResult.new(success=False, error_message=f"搜索失败: {str(e)}")

    def cleanup(self):
        if self.indexer:
            self.indexer.stop_monitoring()
            self.indexer.save_index()
