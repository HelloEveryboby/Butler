from typing import Any
from .abstract_plugin import AbstractPlugin, PluginResult

class UserProfilePlugin(AbstractPlugin):
    """
    A plugin to manage user profile information.
    """
    def get_name(self) -> str:
        return "UserProfilePlugin"

    def valid(self) -> bool:
        return True

    def init(self, logger):
        self.logger = logger
        self.logger.info("UserProfilePlugin initialized.")

    def run(self, command: str, args: dict) -> PluginResult:
        """
        Handles commands related to user profile.
        - "remember my name is [name]": Saves the user's name.
        - "what is my name": Retrieves the user's name.
        """
        if not self.data_storage:
            return PluginResult(success=False, error_message="Data storage not available.")

        if "remember my name is" in command:
            name = args.get("name")
            if name:
                self.data_storage.save(self.get_name(), "user_name", name)
                return PluginResult(success=True, result=f"Okay, I've remembered your name is {name}.")
            else:
                return PluginResult(success=False, error_message="No name provided.")

        elif "what is my name" in command:
            name = self.data_storage.load(self.get_name(), "user_name")
            if name:
                return PluginResult(success=True, result=f"Your name is {name}.")
            else:
                return PluginResult(success=True, result="I don't know your name yet.")

        return PluginResult(success=False, error_message="Unknown command.")

    def stop(self):
        return PluginResult(success=True, result="UserProfilePlugin stopped.")

    def cleanup(self):
        pass

    def status(self) -> Any:
        return PluginResult(success=True, result="UserProfilePlugin is running.")

    def get_commands(self) -> list[str]:
        return ["remember my name is", "what is my name"]
