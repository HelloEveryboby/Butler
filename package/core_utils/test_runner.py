import os
import subprocess
import sys
from pathlib import Path

def run_tests(test_dir="tests", report_dir="data/reports", include_coverage=True):
    """
    运行 pytest 测试并生成 HTML 报告。
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    test_path = project_root / test_dir
    report_path = project_root / report_dir

    if not report_path.exists():
        report_path.mkdir(parents=True, exist_ok=True)

    report_file = report_path / "report.html"

    cmd = [
        sys.executable, "-m", "pytest",
        str(test_path),
        f"--html={report_file}",
        "--self-contained-html"
    ]

    if include_coverage:
        cmd.extend([
            f"--cov={project_root / 'butler'}",
            f"--cov-report=html:{report_path / 'coverage'}"
        ])

    print(f"🚀 开始在 {test_dir} 中运行测试...")
    print(f"📋 报告将生成在: {report_file}")

    try:
        result = subprocess.run(cmd, check=False)

        # 生成简易总结
        print("\n" + "="*40)
        print("         BUTLER 测试执行总结")
        print("="*40)

        if result.returncode == 0:
            print("状态: 🟢 通过 (SUCCESS)")
        else:
            print(f"状态: 🔴 失败 (FAILURE) - 退出码: {result.returncode}")

        print(f"测试目录: {test_dir}")
        print(f"HTML 报告: {report_file}")

        if include_coverage:
            print(f"覆盖率报告: {report_path / 'coverage' / 'index.html'}")

        print("="*40)

        return result.returncode == 0
    except Exception as e:
        print(f"💥 运行测试时出错: {e}")
        return False

if __name__ == "__main__":
    run_tests()
