import os
import json
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CodeExecutionManager:
    def __init__(self, programs_dir="programs"):
        self.programs_dir = programs_dir
        self.registered_programs = {}
        if not os.path.isdir(self.programs_dir):
            logging.warning(f"Programs directory '{self.programs_dir}' not found. Creating it.")
            os.makedirs(self.programs_dir)

    def scan_and_register(self):
        """
        Scans the programs directory, compiles necessary projects, and registers them.
        """
        logging.info(f"Starting scan of programs directory: '{self.programs_dir}'")
        for project_name in os.listdir(self.programs_dir):
            project_path = os.path.join(self.programs_dir, project_name)
            if not os.path.isdir(project_path):
                continue

            manifest_path = os.path.join(project_path, 'manifest.json')
            if not os.path.isfile(manifest_path):
                logging.warning(f"No manifest.json found in '{project_path}', skipping.")
                continue

            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)

                logging.info(f"Processing project '{manifest.get('name', project_name)}'")
                self._compile_and_register_project(project_path, manifest)

            except json.JSONDecodeError:
                logging.error(f"Error decoding manifest.json in '{project_path}'.")
            except Exception as e:
                logging.error(f"Failed to process project '{project_name}': {e}")

        logging.info("Program scan and registration complete.")
        return self.registered_programs

    def _compile_and_register_project(self, project_path, manifest):
        """
        Handles the compilation and registration of a single project.
        """
        name = manifest.get('name')
        language = manifest.get('language')
        build_command = manifest.get('build')
        source_files = manifest.get('source', [])
        executable_name = manifest.get('executable')
        description = manifest.get('description', '')

        if not all([name, language, build_command, source_files, executable_name]):
            logging.error(f"Manifest for '{name}' is missing required fields (name, language, build, source, executable).")
            return

        executable_path = os.path.join(project_path, executable_name)

        # Check if compilation is needed
        needs_compilation = not os.path.exists(executable_path)
        if not needs_compilation:
            exec_mtime = os.path.getmtime(executable_path)
            for src_file in source_files:
                src_path = os.path.join(project_path, src_file)
                if not os.path.exists(src_path) or os.path.getmtime(src_path) > exec_mtime:
                    needs_compilation = True
                    logging.info(f"Source file '{src_file}' is newer than the executable. Recompiling '{name}'.")
                    break

        if needs_compilation:
            logging.info(f"Compiling '{name}'...")

            # Create a dictionary of placeholders to format the build command
            # Use relative paths since the command is run inside the project directory
            source_paths = " ".join(source_files)
            output_path = executable_name # This is also relative to the project dir

            format_dict = {
                'source': source_paths,
                'output': output_path
            }

            try:
                # Use str.format() to replace placeholders
                formatted_command = build_command.format(**format_dict)
                logging.info(f"Executing build command: {formatted_command}")

                # Execute the command from within the project directory
                result = subprocess.run(formatted_command, shell=True, cwd=project_path, check=True, capture_output=True, text=True)
                logging.info(f"Successfully compiled '{name}'.\nCompiler output:\n{result.stdout}")

            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to compile '{name}'.\nCommand: {e.cmd}\nReturn Code: {e.returncode}\nStderr: {e.stderr}")
                return # Do not register if compilation fails
            except KeyError as e:
                logging.error(f"Build command for '{name}' has an invalid placeholder: {e}. Available placeholders: {{source}}, {{output}}.")
                return

        # Register the program
        if os.path.exists(executable_path):
            self.registered_programs[name] = {
                'path': os.path.abspath(executable_path),
                'description': description,
                'language': language,
                'run_command': manifest.get('run') # Store the run command if it exists
            }
            logging.info(f"Successfully registered program: '{name}'")
        else:
            logging.error(f"Build target '{executable_path}' not found after compilation attempt for '{name}'.")

    def get_program(self, name):
        return self.registered_programs.get(name)

    def get_all_programs(self):
        return self.registered_programs

    def get_program_descriptions(self):
        """
        Returns a list of descriptions for all registered programs,
        formatted for the orchestrator.
        """
        descriptions = []
        for name, info in self.registered_programs.items():
            descriptions.append({
                "tool_name": name,
                "description": info.get('description', 'No description available.'),
                # We can add argument details to manifest.json in the future
                "args": ["..."]
            })
        return descriptions

    def execute_program(self, name, args):
        """
        Executes a registered program by name with the given arguments.
        Returns a tuple of (success, output).
        """
        program_info = self.get_program(name)
        if not program_info:
            return False, f"Error: Program '{name}' not found."

        project_dir = os.path.dirname(program_info['path'])
        run_command_template = program_info.get('run_command')

        if run_command_template:
            # Join args into a single string to be safe
            args_str = " ".join(map(str, args))
            command = run_command_template.format(args=args_str)
        else:
            command = [program_info['path']] + list(args)

        logging.info(f"Executing external program with command: {command}")

        try:
            # If command is a string (from run_command), use shell=True
            is_shell_command = isinstance(command, str)
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                cwd=project_dir, # Execute from program's dir
                shell=is_shell_command
            )
            output = f"Program '{name}' executed successfully.\nOutput:\n{result.stdout}"
            logging.info(output)
            return True, result.stdout
        except FileNotFoundError:
            error_msg = f"Error: The executable for '{name}' was not found at '{program_info['path']}'."
            logging.error(error_msg)
            return False, error_msg
        except subprocess.CalledProcessError as e:
            error_msg = f"Error executing '{name}': {e.stderr}"
            logging.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"An unexpected error occurred while executing '{name}': {e}"
            logging.error(error_msg)
            return False, error_msg


if __name__ == '__main__':
    # Example usage for testing
    manager = CodeExecutionManager()
    manager.scan_and_register()
    print("\n--- Registered Programs ---")
    print(json.dumps(manager.get_all_programs(), indent=2))
    print("\n--- Program Descriptions ---")
    print(json.dumps(manager.get_program_descriptions(), indent=2))
    print("---------------------------\n")
