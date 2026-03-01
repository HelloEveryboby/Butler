import json
import time
from typing import Dict, Any, List, Optional
from butler.data_storage import data_storage_manager
from package.core_utils.log_manager import LogManager

class HabitManager:
    """
    Manages user habits, preferences, and long-term context to improve interaction over time.
    """
    def __init__(self):
        self._logger = LogManager.get_logger(__name__)
        self._plugin_name = "SystemHabitManager"
        self._profile_key = "user_habit_profile"
        self._profile: Dict[str, Any] = self._load_profile()

    def _load_profile(self) -> Dict[str, Any]:
        """Loads the user profile from persistent storage."""
        profile = data_storage_manager.load(self._plugin_name, self._profile_key)
        if profile is None:
            # Default empty profile
            return {
                "preferences": {},
                "common_tasks": [],
                "preferred_tools": [],
                "interaction_style": "default",
                "last_updated": 0
            }
        return profile

    def save_profile(self):
        """Saves the current profile to persistent storage."""
        data_storage_manager.save(self._plugin_name, self._profile_key, self._profile)

    def reset_profile(self):
        """Resets the user profile to default and deletes it from storage."""
        self._profile = {
            "preferences": {},
            "common_tasks": [],
            "preferred_tools": [],
            "interaction_style": "default",
            "last_updated": 0
        }
        data_storage_manager.delete(self._plugin_name, self._profile_key)
        self._logger.info("User habit profile has been reset.")

    def update_preference(self, key: str, value: Any):
        """Updates a specific preference in the profile."""
        self._profile["preferences"][key] = value
        self.save_profile()

    def add_common_task(self, task_description: str):
        """Adds a frequently performed task to the profile."""
        if task_description not in self._profile["common_tasks"]:
            self._profile["common_tasks"].append(task_description)
            # Keep only the last 20 tasks
            if len(self._profile["common_tasks"]) > 20:
                self._profile["common_tasks"].pop(0)
            self.save_profile()

    def set_interaction_style(self, style: str):
        """Sets the user's preferred interaction style."""
        self._profile["interaction_style"] = style
        self.save_profile()

    def get_profile_summary(self) -> str:
        """Returns a string summary of the user profile for inclusion in LLM prompts."""
        summary = "用户画像与习惯 (User Habits & Profile):\n"

        # Preferences
        if self._profile["preferences"]:
            summary += "- 用户偏好: " + json.dumps(self._profile["preferences"], ensure_ascii=False) + "\n"

        # Interaction Style
        summary += f"- 交互风格: {self._profile['interaction_style']}\n"

        # Common Tasks
        if self._profile["common_tasks"]:
            summary += "- 高频任务: " + ", ".join(self._profile["common_tasks"][-5:]) + "\n"

        # Preferred Tools
        if self._profile["preferred_tools"]:
            summary += "- 常用工具: " + ", ".join(self._profile["preferred_tools"]) + "\n"

        return summary

    def update_from_reflection(self, insights: Dict[str, Any]):
        """Updates the profile based on insights extracted from a reflection process."""
        if "preferences" in insights:
            self._profile["preferences"].update(insights["preferences"])

        if "interaction_style" in insights:
            self._profile["interaction_style"] = insights["interaction_style"]

        if "common_tasks" in insights:
            for task in insights["common_tasks"]:
                if task not in self._profile["common_tasks"]:
                    self._profile["common_tasks"].append(task)
            # Limit to last 20 tasks
            if len(self._profile["common_tasks"]) > 20:
                self._profile["common_tasks"] = self._profile["common_tasks"][-20:]

        if "preferred_tools" in insights:
            for tool in insights["preferred_tools"]:
                if tool not in self._profile["preferred_tools"]:
                    self._profile["preferred_tools"].append(tool)
            # Limit to last 20 tools
            if len(self._profile["preferred_tools"]) > 20:
                self._profile["preferred_tools"] = self._profile["preferred_tools"][-20:]

        self._profile["last_updated"] = time.time()
        self.save_profile()

# Global instance
habit_manager = HabitManager()
