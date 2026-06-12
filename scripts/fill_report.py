from pathlib import Path
import os
import subprocess
import sys

from utils.file_io import write_text


def subprocess_env(extra=None):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if extra:
        env.update(extra)
    return env


def run(script: Path, *args):
    cmd = [sys.executable, str(script), *map(str, args)]
    subprocess.run(cmd, check=True, text=True, encoding="utf-8", errors="replace", env=subprocess_env())


def main():
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    skill_root = Path(__file__).resolve().parents[1]
    input_docx = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "input" / "template.docx"
    output_docx = Path(sys.argv[3]) if len(sys.argv) > 3 else workspace / "output" / "reports" / "流程测试_实验报告.docx"
    if not input_docx.is_absolute():
        input_docx = workspace / input_docx
    if not output_docx.is_absolute():
        output_docx = workspace / output_docx

    work = workspace / "work"
    output_docx.parent.mkdir(parents=True, exist_ok=True)

    if not (work / "doc_structure.json").exists():
        run(skill_root / "scripts" / "extract_doc_structure.py", workspace, input_docx)
    if not (work / "draft_text_fill_candidates.json").exists():
        run(skill_root / "scripts" / "extract_text_fill_candidates.py", workspace, work / "doc_structure.json")
    if not (work / "refined_text_fill_plan.json").exists():
        message = (
            "ACTION_REQUIRED: review work/doc_structure.json and work/draft_text_fill_candidates.json, "
            "then write work/refined_text_fill_plan.json. Scripts must not copy draft candidates as refined."
        )
        write_text(work / "text_fill_audit.md", "# Text Fill Audit\n\n" + message + "\n")
        print(message)
        raise SystemExit(2)

    env = subprocess_env(
        {
            "LAB_REPORT_INPUT": str(input_docx),
            "LAB_REPORT_STRUCTURE": str(work / "doc_structure.json"),
            "LAB_REPORT_TEXT_PLAN": str(work / "refined_text_fill_plan.json"),
            "LAB_REPORT_OUTPUT": str(output_docx),
            "LAB_REPORT_AUDIT": str(work / "text_fill_audit.md"),
        }
    )
    subprocess.run([sys.executable, str(skill_root / "scripts" / "apply_text_fill_plan.py")], check=True, text=True, encoding="utf-8", errors="replace", env=env)
    print(output_docx)


if __name__ == "__main__":
    main()
