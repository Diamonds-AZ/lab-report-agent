from pathlib import Path
import json
import re
import sys

from docx import Document
from docx.oxml.ns import qn
from utils.file_io import write_json


PLACEHOLDER_RE = re.compile(r"_{3,}|（\s*）|\(\s*\)|【\s*】")
SECTION_KEYWORDS = ("实验过程", "实验任务", "配置", "检查连通性", "检查NAT表项", "实验结果")


def run_info(paragraph):
    info = []
    for idx, run in enumerate(paragraph.runs):
        info.append(
            {
                "run_index": idx,
                "text": run.text,
                "underline": bool(run.underline),
                "bold": bool(run.bold),
                "italic": bool(run.italic),
                "has_many_spaces": bool(re.search(r" {4,}|\t", run.text or "")),
                "has_placeholder": bool(PLACEHOLDER_RE.search(run.text or "")),
            }
        )
    return info


def classify_section(current_path, text):
    path = list(current_path)
    stripped = text.strip()
    if stripped.startswith("一、"):
        path = [stripped]
    elif stripped.startswith("二、"):
        path = [stripped]
    elif stripped.startswith("三、"):
        path = [stripped]
    elif stripped.startswith("实验任务"):
        if path:
            path = [path[0], stripped]
        else:
            path = [stripped]
    elif stripped in ("检查连通性", "检查NAT表项", "配置Basic NAT", "配置NAPT", "配置Easy IP"):
        if len(path) >= 2:
            path = [path[0], path[1], stripped]
        elif path:
            path = [path[0], stripped]
        else:
            path = [stripped]
    return path


def feature_flags(text, previous_text="", next_text="", section_path=None):
    section = " > ".join(section_path or [])
    joined = "\n".join([previous_text or "", text or "", next_text or "", section])
    return {
        "has_many_spaces": bool(re.search(r" {4,}|\t", text or "")),
        "has_underscore": "_" in (text or ""),
        "has_placeholder": bool(PLACEHOLDER_RE.search(text or "")),
        "is_empty": (text or "").strip() == "",
        "is_command_prompt": bool(re.search(r"\[[^\]]+\]", text or "")),
        "is_in_experiment_steps": any(k in joined for k in SECTION_KEYWORDS),
        "nearby_keywords": [k for k in SECTION_KEYWORDS if k in joined],
    }


def main():
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    input_path = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "input" / "template.docx"
    if not input_path.is_absolute():
        input_path = workspace / input_path
    output = workspace / "work" / "doc_structure.json"

    doc = Document(input_path)
    blocks = []
    current_path = []
    paragraph_index = 0
    table_index = 0

    body = doc._element.body
    for element in body:
        if element.tag == qn("w:p"):
            paragraph = doc.paragraphs[paragraph_index]
            text = paragraph.text
            current_path = classify_section(current_path, text)
            blocks.append(
                {
                    "block_id": f"p{paragraph_index}",
                    "block_order": len(blocks),
                    "block_type": "paragraph",
                    "paragraph_index": paragraph_index,
                    "text": text,
                    "style_name": paragraph.style.name if paragraph.style else "",
                    "section_path": current_path,
                    "table_index": None,
                    "row_index": None,
                    "cell_index": None,
                    "run_info": run_info(paragraph),
                    "has_image": bool(paragraph._p.xpath(".//w:drawing")),
                }
            )
            paragraph_index += 1
        elif element.tag == qn("w:tbl"):
            table = doc.tables[table_index]
            for row_index, row in enumerate(table.rows):
                for cell_index, cell in enumerate(row.cells):
                    cell_text = cell.text
                    first_para = cell.paragraphs[0] if cell.paragraphs else None
                    blocks.append(
                        {
                            "block_id": f"t{table_index}_r{row_index}_c{cell_index}",
                            "block_order": len(blocks),
                            "block_type": "table_cell",
                            "paragraph_index": None,
                            "text": cell_text,
                            "style_name": first_para.style.name if first_para and first_para.style else "",
                            "section_path": current_path,
                            "table_index": table_index,
                            "row_index": row_index,
                            "cell_index": cell_index,
                            "run_info": run_info(first_para) if first_para else [],
                            "has_image": bool(cell._tc.xpath(".//w:drawing")),
                        }
                    )
            table_index += 1

    for idx, block in enumerate(blocks):
        block["previous_text"] = blocks[idx - 1]["text"] if idx > 0 else ""
        block["next_text"] = blocks[idx + 1]["text"] if idx + 1 < len(blocks) else ""
        block.update(
            feature_flags(
                block["text"],
                block["previous_text"],
                block["next_text"],
                block.get("section_path"),
            )
        )
        reasons = []
        if block["has_many_spaces"]:
            reasons.append("contains_many_spaces")
        if block["has_placeholder"]:
            reasons.append("contains_placeholder")
        if block["is_empty"] and block["block_type"] == "table_cell":
            reasons.append("empty_table_cell")
        if block["is_command_prompt"]:
            reasons.append("command_prompt")
        if block["is_in_experiment_steps"]:
            reasons.append("experiment_context")
        block["candidate_reason_by_script"] = reasons

    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, {"input_report": str(input_path), "blocks": blocks})
    print(output)


if __name__ == "__main__":
    main()
