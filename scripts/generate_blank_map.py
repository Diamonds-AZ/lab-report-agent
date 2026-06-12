from pathlib import Path
import os
import subprocess
import sys


def main():
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    structure = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "work" / "doc_structure.json"
    output = Path(sys.argv[3]) if len(sys.argv) > 3 else workspace / "work" / "draft_text_fill_candidates.json"
    script = Path(__file__).resolve().parent / "extract_text_fill_candidates.py"
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    subprocess.run([sys.executable, str(script), str(workspace), str(structure), str(output)], check=True, text=True, encoding="utf-8", errors="replace", env=env)


if __name__ == "__main__":
    main()
