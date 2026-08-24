import os
import json
import subprocess
import logging
import shlex
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class CodeExecutionManager:
    """
    CodeExecutionManager scans the programs/ directory, compiles multi-language
    projects (C, C++, Rust, Go, TS/Node, Python), registers their metadata,
    monitors runtime health, and provides unified execution interfaces with
    graceful degradation.
    """

    def __init__(self, programs_dir="programs"):
        self.programs_dir = programs_dir
        self.registered_programs = {}
        if not os.path.isdir(self.programs_dir):
            logging.warning(f"Programs directory '{self.programs_dir}' not found. Creating it.")
            os.makedirs(self.programs_dir)

    def scan_and_register(self):
        """
        Scans the programs directory, normalizes manifests, builds binaries if needed,
        and registers executable metadata with health status tracking.
        """
        logging.info(f"Starting scan of programs directory: '{self.programs_dir}'")
        for project_name in sorted(os.listdir(self.programs_dir)):
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

                norm = self._normalize_manifest(project_path, project_name, manifest)
                logging.info(f"Processing project '{norm['name']}' ({norm['language']})")
                self._compile_and_register_project(project_path, norm)

            except json.JSONDecodeError:
                logging.error(f"Error decoding manifest.json in '{project_path}'.")
            except Exception as e:
                logging.error(f"Failed to process project '{project_name}': {e}")

        logging.info("Program scan and registration complete.")
        return self.registered_programs

    def _normalize_manifest(self, project_path, project_name, manifest):
        """
        Normalizes different manifest.json schemas into a standardized internal representation.
        Handles schema variants for build (object/string), executable (object/string/path),
        entry, source (string/list), and run commands.
        """
        name = manifest.get('name') or manifest.get('id') or project_name
        language = manifest.get('language', 'unknown')
        description = manifest.get('description', '')

        entry = manifest.get('entry')
        source_val = manifest.get('source')
        exec_val = manifest.get('executable')
        build_val = manifest.get('build') if manifest.get('build') is not None else manifest.get('build_command')

        # Extract entry properties if entry is an object or string
        if isinstance(entry, dict):
            if not source_val:
                source_val = entry.get('source')
            if not exec_val:
                exec_val = entry.get('executable')
        elif isinstance(entry, str) and not exec_val and not source_val:
            exec_val = entry

        # Parse build property (string or dict)
        build_command = None
        auto_build = True
        if isinstance(build_val, dict):
            build_command = build_val.get('command')
            auto_build = build_val.get('auto_build', True)
            if not source_val and 'source' in build_val:
                source_val = build_val['source']
            if not exec_val and 'output' in build_val:
                exec_val = build_val['output']
        elif isinstance(build_val, str):
            build_command = build_val

        # Parse executable property (string or dict)
        executable_name = None
        if isinstance(exec_val, dict):
            executable_name = exec_val.get('path')
        elif isinstance(exec_val, str):
            executable_name = exec_val

        # Normalize source files to list of strings
        source_files = []
        if isinstance(source_val, str):
            source_files = [source_val]
        elif isinstance(source_val, list):
            source_files = [str(s) for s in source_val]

        run_command = manifest.get('run')
        if isinstance(run_command, dict):
            run_command = run_command.get('usage') or run_command.get('command')

        return {
            'name': name,
            'language': language,
            'description': description,
            'build_command': build_command,
            'auto_build': auto_build,
            'source_files': source_files,
            'executable_name': executable_name,
            'run_command': run_command,
            'type': manifest.get('type', 'binary' if build_command else 'script'),
            'dependencies': manifest.get('dependencies', {}),
            'capabilities': manifest.get('capabilities', [])
        }

    def _compile_and_register_project(self, project_path, norm):
        """
        Handles compilation and status registration of a normalized project specification.
        Supports Graceful Degradation (DEGRADED / DISABLED) when dependencies or compilers are missing.
        """
        name = norm['name']
        language = norm['language']
        build_command = norm['build_command']
        source_files = norm['source_files']
        executable_name = norm['executable_name']
        description = norm['description']

        if not executable_name and not build_command and not norm['run_command']:
            msg = f"Manifest for '{name}' lacks executable, build_command, or run_command."
            logging.warning(msg)
            self._register_degraded(name, norm, project_path, msg, status="DISABLED")
            return

        executable_path = os.path.join(project_path, executable_name) if executable_name else None

        # Determine if compilation/building is necessary
        needs_compilation = False
        if build_command and norm['auto_build']:
            if not executable_path or not os.path.exists(executable_path):
                needs_compilation = True
            else:
                exec_mtime = os.path.getmtime(executable_path)
                for src_file in source_files:
                    src_path = os.path.join(project_path, src_file)
                    if os.path.exists(src_path) and os.path.getmtime(src_path) > exec_mtime:
                        needs_compilation = True
                        logging.info(f"Source file '{src_file}' is newer than executable for '{name}'. Recompiling.")
                        break

        if needs_compilation and build_command:
            logging.info(f"Compiling/building '{name}'...")

            source_paths = " ".join([shlex.quote(f) for f in source_files])
            output_path = shlex.quote(executable_name) if executable_name else ""

            format_dict = {
                'source': source_paths,
                'output': output_path
            }

            try:
                formatted_command = build_command.format(**format_dict)
                logging.info(f"Executing build command: {formatted_command}")

                shell_chars = {'|', '&', ';', '<', '>', '$', '*', '?', '(', ')', '[', ']', '!', '#', '~'}
                has_shell_meta = any(char in formatted_command for char in shell_chars)

                if not has_shell_meta:
                    command_parts = shlex.split(formatted_command)
                    result = subprocess.run(
                        command_parts, shell=False, cwd=project_path,
                        check=True, capture_output=True, text=True
                    )
                else:
                    result = subprocess.run(
                        formatted_command, shell=True, cwd=project_path,
                        check=True, capture_output=True, text=True
                    )

                logging.info(f"Successfully compiled '{name}'. Output: {result.stdout.strip()}")

            except FileNotFoundError as e:
                msg = f"Build tool or compiler not found for '{name}': {e}"
                logging.warning(f"Graceful degradation for '{name}': {msg}")
                self._register_degraded(name, norm, project_path, msg)
                return
            except subprocess.CalledProcessError as e:
                msg = f"Compilation failed for '{name}': {e.stderr.strip() if e.stderr else str(e)}"
                logging.warning(f"Graceful degradation for '{name}': {msg}")
                self._register_degraded(name, norm, project_path, msg)
                return
            except Exception as e:
                msg = f"Unexpected build error for '{name}': {e}"
                logging.warning(f"Graceful degradation for '{name}': {msg}")
                self._register_degraded(name, norm, project_path, msg)
                return

        # Check executable existence or script availability
        if executable_path and os.path.exists(executable_path):
            self.registered_programs[name] = {
                'path': os.path.abspath(executable_path),
                'description': description,
                'language': language,
                'status': 'ACTIVE',
                'status_message': 'Ready for execution',
                'run_command': norm['run_command'],
                'capabilities': norm['capabilities']
            }
            logging.info(f"Successfully registered program: '{name}' [ACTIVE]")
        elif norm['run_command']:
            # Script or custom command without dedicated binary file
            self.registered_programs[name] = {
                'path': project_path,
                'description': description,
                'language': language,
                'status': 'ACTIVE',
                'status_message': 'Script / custom command ready',
                'run_command': norm['run_command'],
                'capabilities': norm['capabilities']
            }
            logging.info(f"Successfully registered script/command program: '{name}' [ACTIVE]")
        else:
            msg = f"Executable target '{executable_path}' not found after build attempt."
            logging.warning(f"Graceful degradation for '{name}': {msg}")
            self._register_degraded(name, norm, project_path, msg)

    def _register_degraded(self, name, norm, project_path, error_message, status="DEGRADED"):
        """
        Registers a program in DEGRADED or DISABLED status so Butler core is aware of its existence
        without crashing or failing ungracefully when invoked.
        """
        fallback = norm['dependencies'].get('fallback', 'disable') if isinstance(norm['dependencies'], dict) else 'disable'
        self.registered_programs[name] = {
            'path': project_path,
            'description': norm['description'],
            'language': norm['language'],
            'status': status,
            'status_message': error_message,
            'run_command': norm['run_command'],
            'fallback': fallback,
            'capabilities': norm['capabilities']
        }
        logging.info(f"Registered program '{name}' with status [{status}]: {error_message}")

    def get_program(self, name):
        return self.registered_programs.get(name)

    def get_all_programs(self):
        return self.registered_programs

    def get_program_descriptions(self):
        """
        Returns a list of descriptions for all registered programs formatted for orchestrators/LLMs.
        """
        descriptions = []
        for name, info in self.registered_programs.items():
            descriptions.append({
                "tool_name": name,
                "description": info.get('description', 'No description available.'),
                "status": info.get('status', 'UNKNOWN'),
                "capabilities": info.get('capabilities', []),
                "args": ["..."]
            })
        return descriptions

    def execute_program(self, name, args=None):
        """
        Executes a registered program by name with arguments.
        Returns tuple of (success: bool, output: str).
        """
        if args is None:
            args = []

        program_info = self.get_program(name)
        if not program_info:
            return False, f"Error: Program '{name}' not found."

        status = program_info.get('status', 'UNKNOWN')
        if status != 'ACTIVE':
            msg = f"Program '{name}' is unavailable (Status: {status}). Reason: {program_info.get('status_message', 'N/A')}"
            logging.warning(msg)
            return False, msg

        project_dir = program_info['path'] if os.path.isdir(program_info['path']) else os.path.dirname(program_info['path'])
        run_command_template = program_info.get('run_command')

        if run_command_template:
            args_str = " ".join([shlex.quote(str(arg)) for arg in args])
            command = run_command_template.format(args=args_str)
        else:
            command = [program_info['path']] + [str(arg) for arg in args]

        logging.info(f"Executing program '{name}' with command: {command}")

        try:
            is_shell_command = isinstance(command, str)

            if is_shell_command:
                shell_chars = {'|', '&', ';', '<', '>', '$', '*', '?', '(', ')', '[', ']', '!', '#', '~'}
                if not any(char in command for char in shell_chars):
                    try:
                        command = shlex.split(command)
                        is_shell_command = False
                    except ValueError:
                        pass

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                cwd=project_dir,
                shell=is_shell_command
            )
            output = result.stdout.strip()
            logging.info(f"Program '{name}' executed successfully.")
            return True, output
        except FileNotFoundError as e:
            error_msg = f"Error: Executable for '{name}' was not found: {e}"
            logging.error(error_msg)
            return False, error_msg
        except subprocess.CalledProcessError as e:
            error_msg = f"Error executing '{name}': {e.stderr.strip() if e.stderr else str(e)}"
            logging.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error executing '{name}': {e}"
            logging.error(error_msg)
            return False, error_msg


if __name__ == '__main__':
    manager = CodeExecutionManager()
    manager.scan_and_register()
    print("\n--- Registered Programs ---")
    print(json.dumps(manager.get_all_programs(), indent=2))
    print("\n--- Program Descriptions ---")
    print(json.dumps(manager.get_program_descriptions(), indent=2))
    print("---------------------------\n")
