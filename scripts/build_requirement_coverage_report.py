from __future__ import annotations

from pathlib import Path
import json
import sys

from utils.file_io import read_json, write_json, write_text
from utils.fs_safety import configure_utf8_stdio


def load_items(path: Path):
    if not path.exists():
        return []
    data = read_json(path)
    return data.get("items", data if isinstance(data, list) else [])


def main():
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    requirements = load_items(workspace / "work" / "requirement_items.json")
    text_plan = read_json(workspace / "work" / "refined_text_fill_plan.json") if (workspace / "work" / "refined_text_fill_plan.json").exists() else {}
    image_plan = read_json(workspace / "work" / "refined_image_plan.json") if (workspace / "work" / "refined_image_plan.json").exists() else {}
    text_covered = set()
    image_covered = set()
    for item in text_plan.get("items", []):
        text_covered.update(item.get("covered_requirement_ids") or item.get("requirement_ids") or [])
    for item in image_plan.get("items", []):
        image_covered.update(item.get("covered_requirement_ids") or item.get("requirement_ids") or [])
    missing = []
    details = []
    for req in requirements:
        rid = req.get("requirement_id")
        has_text = rid in text_covered or not text_covered
        has_image = (rid in image_covered) if req.get("requires_image") else True
        status = "covered" if has_text and has_image else "missing"
        if status == "missing":
            missing.append(rid)
        details.append(
            {
                "requirement_id": rid,
                "requires_image": req.get("requires_image"),
                "text_covered": has_text,
                "image_covered": has_image,
                "status": status,
                "original_text": req.get("original_text"),
            }
        )
    report = {
        "requirement_count": len(requirements),
        "real_missing_requirement": missing,
        "real_missing_requirement_count": len(missing),
        "details": details,
    }
    write_json(workspace / "work" / "requirement_coverage_report.json", report)
    lines = ["# Requirement Coverage Report", "", f"- requirement_count: {len(requirements)}", f"- real_missing_requirement_count: {len(missing)}", ""]
    for detail in details:
        lines.append(f"- {detail['requirement_id']}: {detail['status']} | text={detail['text_covered']} | image={detail['image_covered']} | {detail['original_text']}")
    write_text(workspace / "work" / "requirement_coverage_report.md", "\n".join(lines) + "\n")
    print(workspace / "work" / "requirement_coverage_report.md")


if __name__ == "__main__":
    main()
