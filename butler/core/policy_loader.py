import os

def load_butler_policy() -> str:
    """
    Loads BUTLER.md policy if it exists and returns it as a prompt-ready string.
    """
    # Navigate up to repository root (butler/core/policy_loader.py -> butler/core -> butler -> root)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    policy_path = os.path.join(project_root, "BUTLER.md")
    if os.path.exists(policy_path):
        try:
            with open(policy_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return f"\n\n### 🛡️ Butler Execution Guidelines (BUTLER.md)\n{content}\n"
        except Exception:
            pass
    return ""
