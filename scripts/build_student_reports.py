from pathlib import Path
import json
import re
import shutil
import sys

from docx import Document
from utils.file_io import read_text, write_json


def scalar(text: str, key: str, default=""):
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(key + ":"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return default


def section_lines(text: str, section: str):
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == section + ":":
            start = idx + 1
            break
    if start is None:
        return []
    out = []
    for line in lines[start:]:
        if line and not line.startswith((" ", "\t")) and re.match(r"^[A-Za-z_][\w-]*:", line):
            break
        out.append(line)
    return out


def nested_bool(text: str, section: str, key: str):
    for line in section_lines(text, section):
        stripped = line.strip()
        if stripped.startswith(key + ":"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'").lower() == "true"
    return False


def inline_list(text: str, key: str):
    value = scalar(text, key, "")
    if not value.startswith("[") or not value.endswith("]"):
        return []
    body = value[1:-1].strip()
    if not body:
        return []
    return [x.strip().strip('"').strip("'") for x in body.split(",") if x.strip()]


def parse_students(path: Path):
    if not path.exists():
        return []
    students = []
    current = None
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            if current:
                students.append(current)
            current = {}
            line = line[2:].strip()
            if ":" in line:
                k, v = line.split(":", 1)
                current[k.strip()] = v.strip().strip('"').strip("'")
            continue
        if current is not None and ":" in line:
            k, v = line.split(":", 1)
            current[k.strip()] = v.strip().strip('"').strip("'")
    if current:
        students.append(current)
    return students


def selected_students(task_text: str, roster_students):
    mode = scalar(task_text, "target_mode", "single")
    targets = set(inline_list(task_text, "target_students"))
    if mode == "all":
        return roster_students
    if mode in {"single", "subset"} and targets:
        chosen = []
        for student in roster_students:
            keys = {student.get("id", ""), student.get("name", ""), student.get("output_name", "")}
            if keys & targets:
                chosen.append(student)
        return chosen[:1] if mode == "single" else chosen
    return roster_students[:1]


def replace_in_runs(paragraph, pairs):
    for run in paragraph.runs:
        text = run.text or ""
        for old, new in pairs:
            text = text.replace(old, new)
        run.text = text


def fill_identity(doc, student):
    pairs = [
        ("待填写", student.get("name", "")),
        ("学号-姓名", f"{student.get('id', '')}-{student.get('name', '')}".strip("-")),
        ("姓名", f"姓名：{student.get('name', '')}"),
        ("学号", f"学号：{student.get('id', '')}"),
        ("班级", f"班级：{student.get('class_name', '')}"),
    ]
    for paragraph in doc.paragraphs:
        text = paragraph.text
        if any(key in text for key in ("姓名", "学号", "班级", "待填写")):
            replace_in_runs(paragraph, pairs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_text = cell.text
                if cell_text.strip() in {"姓名", "学号", "班级"}:
                    continue
                for paragraph in cell.paragraphs:
                    if any(key in paragraph.text for key in ("姓名", "学号", "班级", "待填写")):
                        replace_in_runs(paragraph, pairs)


def safe_name(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip() or "实验报告.docx"


def output_name(student, task_name):
    if student.get("output_name"):
        return safe_name(student["output_name"])
    sid = student.get("id", "unknown")
    name = student.get("name", "student")
    return safe_name(f"{sid}_{name}_{task_name}.docx")


def main():
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    base_report = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "output" / "reports" / "base_report.docx"
    if not base_report.is_absolute():
        base_report = workspace / base_report

    task_path = workspace / "configs" / "task.yaml"
    task_text = read_text(task_path) if task_path.exists() else ""
    roster_students = parse_students(workspace / "configs" / "roster.yaml")
    students = selected_students(task_text, roster_students)
    task_name = scalar(task_text, "task_name", "实验报告")
    output_dir = workspace / scalar(task_text, "output_dir", "output/reports")
    fill_identity_fields = nested_bool(task_text, "identity_rules", "fill_identity_fields")
    use_identity_in_report = nested_bool(task_text, "identity_rules", "use_identity_in_report")

    output_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        "base_report": str(base_report),
        "mode": scalar(task_text, "target_mode", "single"),
        "identity_enabled": bool(fill_identity_fields or use_identity_in_report),
        "reports": [],
    }

    if not students:
        target = output_dir / "流程测试_实验报告.docx"
        shutil.copy2(base_report, target)
        plan["reports"].append({"student": None, "output": str(target), "status": "copied_no_roster"})
    else:
        for student in students:
            target = output_dir / output_name(student, task_name)
            shutil.copy2(base_report, target)
            if fill_identity_fields or use_identity_in_report:
                doc = Document(target)
                fill_identity(doc, student)
                doc.save(target)
            plan["reports"].append({"student": student, "output": str(target), "status": "generated"})

    out = workspace / "work" / "student_report_plan.json"
    write_json(out, plan)
    print(out)


if __name__ == "__main__":
    main()
