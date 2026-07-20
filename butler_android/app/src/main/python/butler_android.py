import os
import sys
import logging
import json
import traceback
from butler.core.skill_manager import SkillManager

logger = logging.getLogger("ButlerAndroid")

skill_manager = None

# Cache Java Log class globally at module-level to avoid expensive JNI lookup on hot-path stdout/stderr logging
try:
    from java import jclass
    Log = jclass("android.util.Log")
except ImportError:
    Log = None

class LogStream:
    def __init__(self, tag, is_stderr=False):
        self.tag = tag
        self.is_stderr = is_stderr
        self.buffer = ""

    def write(self, message):
        self.buffer += message
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                if Log is not None:
                    if self.is_stderr:
                        Log.e(self.tag, line)
                    else:
                        Log.i(self.tag, line)
                else:
                    # Fallback if running outside Chaquopy (e.g. mock unit tests)
                    if self.is_stderr:
                        sys.__stderr__.write(line + "\n")
                    else:
                        sys.__stdout__.write(line + "\n")

    def flush(self):
        if self.buffer.strip():
            if Log is not None:
                if self.is_stderr:
                    Log.e(self.tag, self.buffer)
                else:
                    Log.i(self.tag, self.buffer)
            else:
                if self.is_stderr:
                    sys.__stderr__.write(self.buffer + "\n")
                else:
                    sys.__stdout__.write(self.buffer + "\n")
            self.buffer = ""

def redirect_streams():
    try:
        sys.stdout = LogStream("Butler_Python", is_stderr=False)
        sys.stderr = LogStream("Butler_Python", is_stderr=True)
    except Exception as e:
        logger.error(f"Failed to redirect streams: {e}")

def initialize(files_dir=None):
    global skill_manager
    # Use provided files_dir or fallback to platform standard
    if not files_dir:
        files_dir = os.environ.get("CHAKUOPY_FILES_DIR", "/data/data/com.butler.app/files")

    skills_path = os.path.join(files_dir, "skills")

    logger.info(f"Initializing Butler SkillManager at {skills_path}")
    skill_manager = SkillManager(skills_dir=skills_path)
    skill_manager.load_skills()

    # Redirect sys.stdout and sys.stderr to android Logcat under tag Butler_Python
    redirect_streams()

def call_plugin(skill_id, action, params_json):
    if not skill_manager:
        return json.dumps({
            "status": "error",
            "error_type": "InitializationError",
            "message": "SkillManager not initialized",
            "traceback": ""
        })

    try:
        params = json.loads(params_json)
        # Execute skill via Chaquopy and return structured result
        result = skill_manager.execute(skill_id, action, **params)
        return json.dumps({
            "status": "success",
            "data": result
        })
    except Exception as e:
        tb = traceback.format_exc()
        if Log is not None:
            Log.e("Butler_Python", f"Error executing plugin {skill_id} action {action}: {str(e)}\n{tb}")
        else:
            # Fallback for mock environments
            sys.__stderr__.write(f"Error executing plugin {skill_id}: {str(e)}\n{tb}\n")

        return json.dumps({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "traceback": tb
        })

def cleanup():
    global skill_manager
    if skill_manager:
        skill_manager.stop_monitoring()
