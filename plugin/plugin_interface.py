from abc import ABCMeta, abstractmethod
from datetime import datetime
from typing import Any, Optional, Dict, List
import logging
import os
from butler.data_storage import DataStorageManager
from package.core_utils.log_manager import LogManager
from butler.core.hybrid_link import HybridLinkClient


class PluginResult:
    def __init__(self):
        # Result content, mainly for AI reference
        self.result = None
        # Whether the brain (LLM) needs to be called again after execution
        self.need_call_brain = False
        # Error message, None if no error
        self.error_message = None
        # Execution status, True for success, False for failure
        self.success = True
        # Execution time in seconds (optional)
        self.execution_time = None
        # Plugin metadata (e.g., name, version)
        self.metadata = {}
        # Status string (optional)
        self.status = None
        # Additional data payload
        self.additional_data = {}
        # Timestamp of completion
        self.timestamp = datetime.now()

    @staticmethod
    def new(
        result: Any,
        need_call_brain: bool = False,
        success: bool = True,
        error_message: str = None,
        execution_time: float = None,
        metadata: dict = None,
        status: str = None,
        additional_data: dict = None,
    ):
        r = PluginResult()
        r.result = result
        r.need_call_brain = need_call_brain
        r.success = success
        r.error_message = error_message
        r.execution_time = execution_time
        r.metadata = metadata if metadata else {}
        r.status = status
        r.additional_data = additional_data if additional_data else {}
        r.timestamp = datetime.now()
        return r

    def is_success(self):
        return self.success

    def has_error(self):
        return self.error_message is not None

    def add_metadata(self, key: str, value):
        self.metadata[key] = value

    def get_metadata(self, key: str):
        return self.metadata.get(key)

    def __str__(self):
        return (
            f"PluginResult(result={self.result}, need_call_brain={self.need_call_brain}, "
            f"success={self.success}, error_message={self.error_message}, execution_time={self.execution_time}, "
            f"metadata={self.metadata}, status={self.status}, additional_data={self.additional_data})"
        )


class AbstractPlugin(metaclass=ABCMeta):
    def __init__(self):
        self.data_storage: Optional[DataStorageManager] = None
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self._hybrid_clients: Dict[str, HybridLinkClient] = {}

    def get_root_dir(self) -> str:
        """Returns the project root directory."""
        # plugin/plugin_interface.py -> plugin -> project_root
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def get_hybrid_client(self, module_name: str) -> Optional[HybridLinkClient]:
        """
        Returns a HybridLinkClient for the specified native module.
        Automatically resolves the executable path based on the module's manifest.json.
        """
        if module_name in self._hybrid_clients:
            return self._hybrid_clients[module_name]

        root_dir = self.get_root_dir()
        manifest_path = os.path.join(root_dir, "programs", module_name, "manifest.json")

        if not os.path.exists(manifest_path):
            self.logger.error(f"Manifest not found for module: {module_name}")
            return None

        try:
            import json

            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            executable_rel_path = manifest.get("executable")
            if not executable_rel_path:
                self.logger.error(
                    f"No executable specified in manifest for module: {module_name}"
                )
                return None

            executable_path = os.path.join(
                root_dir, "programs", module_name, executable_rel_path
            )

            # Auto-build if executable is missing
            if not os.path.exists(executable_path):
                self.logger.info(
                    f"Executable not found for {module_name}. Attempting to build..."
                )
                self._build_native_module(module_name, root_dir)

            if os.path.exists(executable_path):
                client = HybridLinkClient(
                    executable_path, cwd=os.path.dirname(executable_path)
                )
                self._hybrid_clients[module_name] = client
                return client
            else:
                self.logger.error(
                    f"Failed to resolve executable for module: {module_name}"
                )
                return None
        except Exception as e:
            self.logger.error(f"Error loading hybrid client for {module_name}: {e}")
            return None

    def _build_native_module(self, module_name: str, root_dir: str):
        """Attempts to build the native module using its build.sh or manifest instructions."""
        module_dir = os.path.join(root_dir, "programs", module_name)
        build_sh = os.path.join(module_dir, "build.sh")

        import subprocess

        if os.path.exists(build_sh):
            try:
                self.logger.info(f"Running build.sh for {module_name}...")
                subprocess.run(["bash", "build.sh"], check=True, cwd=module_dir)
            except Exception as e:
                self.logger.error(f"build.sh failed for {module_name}: {e}")
        else:
            # Try build command from manifest
            manifest_path = os.path.join(module_dir, "manifest.json")
            try:
                import json

                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                build_cmd = manifest.get("build")
                if build_cmd:
                    self.logger.info(
                        f"Running build command for {module_name}: {build_cmd}"
                    )
                    subprocess.run(build_cmd, shell=True, check=True, cwd=module_dir)
            except Exception as e:
                self.logger.error(f"Manifest build failed for {module_name}: {e}")

    def set_data_storage(self, data_storage_manager: DataStorageManager):
        """Sets the data storage manager for the plugin."""
        self.data_storage = data_storage_manager

    def valid(self) -> bool:
        """Check if the plugin is valid to be loaded."""
        return True

    def init(self, logger: logging.Logger):
        """Initialize the plugin with a logger."""
        self.logger = logger

    @abstractmethod
    def get_name(self) -> str:
        """Internal name of the plugin."""
        pass

    def get_chinese_name(self) -> str:
        """Display name of the plugin in Chinese."""
        return self.get_name()

    def get_description(self) -> str:
        """Brief description of the plugin."""
        return ""

    def get_parameters(self) -> Dict[str, str]:
        """Description of the parameters this plugin accepts."""
        return {}

    def on_startup(self):
        """Called when the plugin system starts up."""
        pass

    def on_shutdown(self):
        """Called when the plugin system shuts down."""
        for module_name, client in self._hybrid_clients.items():
            self.logger.info(f"Stopping hybrid client for {module_name}")
            client.stop()

    def on_pause(self):
        """Called when the plugin is paused."""
        pass

    def on_resume(self):
        """Called when the plugin is resumed."""
        pass

    @abstractmethod
    def run(self, command: str, args: dict) -> PluginResult:
        """Main execution entry point for the plugin."""
        pass

    def stop(self) -> Any:
        """Stop the plugin execution if running."""
        return None

    def cleanup(self):
        """Perform cleanup before unloading."""
        pass

    def status(self) -> Any:
        """Return the current status of the plugin."""
        return "running"

    def get_commands(self) -> List[str]:
        """Returns a list of commands that this plugin can handle."""
        return []

    def get_match_type(self) -> str:
        """Returns the match type for the commands: 'exact', 'prefix', or 'contains'."""
        return "contains"
