import os
from package.workflow_manager import WorkflowManager

def create_example_config(filepath: str):
    """Creates an example workflow configuration file."""
    with open(filepath, 'w') as f:
        f.write("# Module Cost Position Dependencies\n")
        f.write("package.entrypoint 0 start_pos\n")
        f.write("package.moduleA 10 moduleA_pos package.entrypoint\n")
        f.write("package.moduleB 5 moduleB_pos package.entrypoint\n")
        f.write("package.moduleC 2 moduleC_pos package.moduleA,package.moduleB\n")
        f.write("package.finalizer 0 end_pos package.moduleC\n")

def create_dummy_module(filepath: str, module_name: str):
    """Creates a dummy module file with a run() function."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(f"def run():\n")
        f.write(f"    print(f'--- Running dummy module: {module_name} ---')\n")

if __name__ == "__main__":
    # 1. Setup example configuration and dummy modules
    config_file = "example_config.txt"
    create_example_config(config_file)

    # Create dummy module files for the example
    create_dummy_module("package/entrypoint.py", "entrypoint")
    create_dummy_module("package/moduleA.py", "moduleA")
    create_dummy_module("package/moduleB.py", "moduleB")
    create_dummy_module("package/moduleC.py", "moduleC")
    create_dummy_module("package/finalizer.py", "finalizer")

    # 2. Initialize the WorkflowManager
    # Set stop_on_error to False to see it continue even if a module fails.
    manager = WorkflowManager(stop_on_error=True)

    # 3. Define the start and end points of the workflow
    start_module = "package.entrypoint"
    end_module = "package.finalizer"

    # 4. Run the workflow
    print("--- Starting Workflow Execution ---")
    manager.run(config_file, start_module, end_module)
    print("--- Workflow Execution Finished ---")

    # 5. Clean up the dummy files
    os.remove(config_file)
    os.remove("package/entrypoint.py")
    os.remove("package/moduleA.py")
    os.remove("package/moduleB.py")
    os.remove("package/moduleC.py")
    os.remove("package/finalizer.py")
