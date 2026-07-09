#!/usr/bin/env python3
"""
scripts/dependency_check.py
Generates a dependency_report.json by scanning Python files for imports and
comparing them with requirements.txt (best-effort static analysis).

Usage: python3 scripts/dependency_check.py
Outputs: dependency_report.json at repo root
"""

import ast
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
PY_FILES = [p for p in ROOT.rglob("*.py") if "venv" not in p.parts and ".venv" not in p.parts and "site-packages" not in p.parts]

STANDARD_LIBS = {
    'os','sys','json','re','math','time','pathlib','typing','argparse','subprocess','logging',
    'itertools','collections','contextlib','threading','asyncio','dataclasses','builtins','inspect',
}


def extract_top_level_modules_from_file(path: Path):
    modules = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return modules
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                top = n.name.split(".")[0]
                modules.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                modules.add(top)
    return modules


def read_requirements(req_path: Path):
    reqs = set()
    if not req_path.exists():
        return reqs
    for line in req_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split()[0]
        pkg = pkg.split(";", 1)[0]
        # normalize common casings
        reqs.add(pkg.strip())
    return reqs


def guess_package_for_module(mod):
    # Best-effort: assume top-level module name equals pip package name
    # Special cases mapping
    mapping = {
        'cv2': 'opencv-python',
        'PIL': 'Pillow',
        'yaml': 'PyYAML',
        'bs4': 'beautifulsoup4',
        'pypdf': 'pypdf',
        'pdfplumber': 'pdfplumber',
        'sklearn': 'scikit-learn',
        'np': 'numpy',
    }
    return mapping.get(mod, mod)


def main():
    used_modules = set()
    files_by_module = defaultdict(list)
    for f in PY_FILES:
        mods = extract_top_level_modules_from_file(f)
        for m in mods:
            used_modules.add(m)
            files_by_module[m].append(str(f.relative_to(ROOT)))

    reqs = read_requirements(ROOT / "requirements.txt")

    used_pkgs = set(guess_package_for_module(m) for m in used_modules if m and m not in STANDARD_LIBS and not m.startswith("_") )

    missing_in_requirements = sorted([p for p in used_pkgs if not any(p.lower() in r.lower() for r in reqs)])
    unused_requirements = sorted([r for r in reqs if not any(r.lower().split("=",1)[0] in m.lower() for m in used_pkgs)])

    report = {
        "repo_root": str(ROOT),
        "used_modules_count": len(used_modules),
        "used_top_level_modules": sorted(list(used_modules)),
        "used_pkgs_guess": sorted(list(used_pkgs)),
        "requirements_list": sorted(list(reqs)),
        "missing_in_requirements_guess": missing_in_requirements,
        "unused_requirements_guess": unused_requirements,
        "files_by_module_sample": {k: files_by_module[k][:20] for k in list(files_by_module)[:200]}
    }

    out = ROOT / "dependency_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Wrote report to {out}")


if __name__ == "__main__":
    main()
