import os
import sys
import logging
from butler.core.skill_manager import SkillManager

logger = logging.getLogger("ButlerAndroid")

skill_manager = None

def initialize(files_dir=None):
    global skill_manager
    # Use provided files_dir or fallback to platform standard
    if not files_dir:
        files_dir = os.environ.get("CHAKUOPY_FILES_DIR", "/data/data/com.butler.app/files")

    skills_path = os.path.join(files_dir, "skills")

    logger.info(f"Initializing Butler SkillManager at {skills_path}")
    skill_manager = SkillManager(skills_dir=skills_path)
    skill_manager.load_skills()

def call_plugin(skill_id, action, params_json):
    if not skill_manager:
        return "Error: SkillManager not initialized"

    try:
        import json
        params = json.loads(params_json)
        # Execute skill via Chaquopy sandbox
        result = skill_manager.execute(skill_id, action, **params)
        return json.dumps(result)
    except Exception as e:
        return f"Error: {str(e)}"

def cleanup():
    if skill_manager:
        skill_manager.stop_monitoring()
