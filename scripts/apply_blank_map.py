from pathlib import Path
import os
import subprocess
import sys


def main():
    script = Path(__file__).resolve().parent / "apply_text_fill_plan.py"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if "LAB_REPORT_BLANK_MAP" in env and "LAB_REPORT_TEXT_PLAN" not in env:
        env["LAB_REPORT_TEXT_PLAN"] = env["LAB_REPORT_BLANK_MAP"]
    subprocess.run([sys.executable, str(script)], check=True, text=True, encoding="utf-8", errors="replace", env=env)


if __name__ == "__main__":
    main()
