from __future__ import annotations

from pathlib import Path
import re
import sys

from utils.file_io import read_json, write_json, write_text
from utils.fs_safety import configure_utf8_stdio


NUMBERED_RE = re.compile(r"(?:^|\n|\s)(（\d+）|\(\d+\)|\d+[.、]|[一二三四五六七八九十]+[、.])\s*")


def split_requirements(text: str):
    matches = list(NUMBERED_RE.finditer(text))
    items = []
    if not matches:
        return items
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if len(chunk) < 8:
            continue
        items.append(chunk)
    return items


def flags_for(text: str):
    lower = text.lower()
    return {
        "requires_code": any(k in lower for k in ("代码", "sql", "命令", "程序", "函数", "class", "select", "grant", "display")),
        "requires_image": any(k in text for k in ("截图", "运行结果", "结果截图", "界面")),
        "requires_explanation": any(k in text for k in ("说明", "分析", "原因", "解释", "总结")),
        "requires_result": any(k in text for k in ("结果", "输出", "验证", "测试", "查询")),
    }


def looks_like_code_fragment(text: str) -> bool:
    code_markers = ("#include", "printf(", "scanf(", "return ", "void ", "int main", "{", "}")
    marker_count = sum(marker in text for marker in code_markers)
    return marker_count >= 2


def main():
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    structure_path = workspace / "work" / "doc_structure.json"
    if not structure_path.exists():
        raise SystemExit("Missing work/doc_structure.json")
    structure = read_json(structure_path)
    candidates = []
    for block in structure.get("blocks", []):
        text = block.get("text", "")
        if text:
            candidates.extend(split_requirements(text))
    for para in structure.get("paragraphs", []):
        text = para.get("text", "")
        if text:
            candidates.extend(split_requirements(text))
    for table in structure.get("tables", []):
        for row in table.get("rows", []):
            for cell in row.get("cells", []):
                text = cell.get("text", "")
                if text:
                    candidates.extend(split_requirements(text))

    seen = set()
    items = []
    for raw in candidates:
        normalized = re.sub(r"\s+", " ", raw).strip()
        if looks_like_code_fragment(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        item = {
            "requirement_id": f"REQ-{len(items)+1:03d}",
            "original_text": normalized,
            "source_section": "模板编号任务",
            "nearby_context": normalized[:160],
            **flags_for(normalized),
        }
        items.append(item)

    report = {
        "requirement_count": len(items),
        "items": items,
    }
    write_json(workspace / "work" / "requirement_items.json", report)
    lines = ["# Requirement Items", "", f"- requirement_count: {len(items)}", ""]
    for item in items:
        lines.extend(
            [
                f"## {item['requirement_id']}",
                "",
                item["original_text"],
                "",
                f"- requires_code: {item['requires_code']}",
                f"- requires_image: {item['requires_image']}",
                f"- requires_explanation: {item['requires_explanation']}",
                f"- requires_result: {item['requires_result']}",
                "",
            ]
        )
    write_text(workspace / "work" / "requirement_items.md", "\n".join(lines))
    print(workspace / "work" / "requirement_items.json")


if __name__ == "__main__":
    main()
