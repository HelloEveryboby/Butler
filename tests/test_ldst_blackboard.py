import unittest
import os
import shutil
from pathlib import Path
from butler.core.skill_manager import SkillManager
from butler.core.algorithms import LDSTResolver
from butler.core.blackboard import blackboard

class TestLDSTandBlackboard(unittest.TestCase):
    def setUp(self):
        self.test_skills_dir = Path("test_skills_ldst")
        self.test_skills_dir.mkdir(exist_ok=True)

        # Create Skill A (Provider)
        skill_a = self.test_skills_dir / "skill_a"
        skill_a.mkdir()
        (skill_a / "SKILL.md").write_text("""---
skill_name: skill_a
provides:
  - data.source
---
# Skill A
""", encoding='utf-8')

        # Create Skill B (Consumer)
        skill_b = self.test_skills_dir / "skill_b"
        skill_b.mkdir()
        (skill_b / "SKILL.md").write_text("""---
skill_name: skill_b
requires:
  data.source: any
---
# Skill B
""", encoding='utf-8')

        # Create Skill C (High Risk)
        skill_c = self.test_skills_dir / "skill_c"
        skill_c.mkdir()
        (skill_c / "SKILL.md").write_text("""---
skill_name: skill_c
risk: high
---
# Skill C
""", encoding='utf-8')

        self.manager = SkillManager(skills_dir="test_skills_ldst")
        self.manager.load_skills()

    def tearDown(self):
        if self.test_skills_dir.exists():
            shutil.rmtree(self.test_skills_dir)

    def test_ldst_resolution(self):
        resolver = LDSTResolver(self.manager.manifests)
        chain = resolver.resolve("skill_b")
        self.assertEqual(chain, ["skill_a", "skill_b"])

    def test_risk_escalation(self):
        # Normal chain
        chain_low = ["skill_a", "skill_b"]
        risk_low = self.manager._check_risk_escalation(chain_low)
        self.assertEqual(risk_low, "low")

        # Chain with high risk skill
        chain_high = ["skill_a", "skill_c"]
        risk_high = self.manager._check_risk_escalation(chain_high)
        self.assertEqual(risk_high, "high")

    def test_blackboard_lifecycle(self):
        blackboard.write("test_key", "test_value", ttl=0.1)
        self.assertEqual(blackboard.read_snapshot("test_key"), "test_value")

        import time
        time.sleep(0.2)
        self.assertIsNone(blackboard.read_snapshot("test_key"))

if __name__ == "__main__":
    unittest.main()
