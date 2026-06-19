from butler.core.memory.plugin_interface import AbstractPlugin, PluginResult

class UserProfilePlugin(AbstractPlugin):
    def get_name(self) -> str:
        return "UserProfilePlugin"

    def get_commands(self) -> list:
        return ["remember", "what is my name"]

    def run(self, command: str, args: dict) -> PluginResult:
        if "remember" in command:
            name = args.get("name")
            self.data_storage.save("UserProfilePlugin", "name", name)
            return PluginResult.new(result=f"Okay, I've remembered your name is {name}")
        elif "what is my name" in command:
            name = self.data_storage.load("UserProfilePlugin", "name")
            return PluginResult.new(result=f"Your name is {name}")
        return PluginResult.new(success=False, error_message="Unknown command")
