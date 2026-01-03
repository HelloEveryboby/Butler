import json
import subprocess
import logging

logger = logging.getLogger(__name__)

class ExternalProgramManager:
    """
    Manages the loading and execution of external programs defined in a JSON registry.
    """
    def __init__(self, registry_path="external_programs.json"):
        """
        Initializes the manager and loads the program registry.

        Args:
            registry_path (str): The path to the JSON file containing program definitions.
        """
        self.registry_path = registry_path
        self.programs = self._load_registry()

    def _load_registry(self):
        """
        Loads the external program registry from the specified JSON file.
        """
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                programs = json.load(f)
            logger.info(f"Successfully loaded {len(programs)} external programs from '{self.registry_path}'.")
            return {prog["name"]: prog for prog in programs}
        except FileNotFoundError:
            logger.warning(f"External program registry not found at '{self.registry_path}'. No external programs will be available.")
            return {}
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse the external program registry at '{self.registry_path}': {e}", exc_info=True)
            return {}

    def get_program_descriptions(self):
        """
        Returns a list of descriptions for all registered programs,
        formatted for inclusion in an AI prompt.
        """
        if not self.programs:
            return []

        descriptions = []
        for name, data in self.programs.items():
            desc = f"- Tool Name: `{name}`\n"
            desc += f"  - Description: {data.get('description', 'No description provided.')}\n"
            desc += f"  - Arguments: {data.get('args_prompt', 'No argument information provided.')}"
            descriptions.append(desc)
        return descriptions

    def execute_program(self, name, args=None):
        """
        Executes a registered program by its name.

        Args:
            name (str): The name of the program to execute.
            args (list, optional): A list of string arguments to pass to the program. Defaults to None.

        Returns:
            A tuple (success: bool, output: str) containing the result of the execution.
        """
        if args is None:
            args = []

        program_data = self.programs.get(name)
        if not program_data:
            error_message = f"Error: Program '{name}' not found in the registry."
            logger.error(error_message)
            return False, error_message

        path = program_data.get("path")
        if not path:
            error_message = f"Error: Program '{name}' is missing a 'path' in the registry."
            logger.error(error_message)
            return False, error_message

        command = [path] + args
        try:
            logger.info(f"Executing external program: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8'
            )
            output = f"--- STDOUT ---\n{result.stdout}\n"
            if result.stderr:
                output += f"--- STDERR ---\n{result.stderr}\n"
            logger.info(f"Program '{name}' executed successfully.")
            return True, output
        except FileNotFoundError:
            error_message = f"Error executing '{name}': The executable at '{path}' was not found."
            logger.error(error_message)
            return False, error_message
        except subprocess.CalledProcessError as e:
            error_message = (
                f"Error executing '{name}': Program returned a non-zero exit code {e.returncode}.\n"
                f"--- STDOUT ---\n{e.stdout}\n"
                f"--- STDERR ---\n{e.stderr}\n"
            )
            logger.error(error_message)
            return False, error_message
        except Exception as e:
            error_message = f"An unexpected error occurred while trying to execute '{name}': {e}"
            logger.error(error_message, exc_info=True)
            return False, error_message
