from __future__ import annotations

from pathlib import Path
import re
import sys

from utils.file_io import read_json, write_json


WIDE_SPACE_RE = re.compile(r" {4,}|\t+")
PLACEHOLDER_RE = re.compile(r"_{3,}|\(\s*\)|（\s*）")


def structural_role(block: dict) -> str:
    text = block.get("text") or ""
    if block.get("block_type") == "table_cell" and block.get("is_empty"):
        return "empty_table_cell"
    if block.get("is_empty"):
        return "empty_paragraph"
    if PLACEHOLDER_RE.search(text):
        return "placeholder_text"
    if WIDE_SPACE_RE.search(text):
        return "wide_space_text"
    if len(text.strip()) <= 60 and any(mark in text for mark in ("：", ":", "一、", "二、", "三、", "1、", "2、", "3、")):
        return "short_heading_or_prompt"
    return "context_block"


def include_block(block: dict) -> bool:
    text = block.get("text") or ""
    if block.get("is_empty"):
        return True
    if PLACEHOLDER_RE.search(text) or WIDE_SPACE_RE.search(text):
        return True
    if len(text.strip()) <= 140:
        return True
    return any(token in text for token in ("实验报告模板", "实验目的", "实验任务", "实验流程", "程序流程图", "实验现象", "实验结果", "实验总结"))


def material_item(idx: int, block: dict) -> dict:
    return {
        "candidate_id": f"text_material_{idx:03d}",
        "block_id": block["block_id"],
        "material_type": "document_structure_fact",
        "structural_role": structural_role(block),
        "block_type": block.get("block_type"),
        "text": block.get("text", ""),
        "is_empty": bool(block.get("is_empty")),
        "table_index": block.get("table_index"),
        "row_index": block.get("row_index"),
        "cell_index": block.get("cell_index"),
        "slot_index": 0,
        "left_context": (block.get("previous_text") or "")[-220:],
        "right_context": (block.get("next_text") or "")[:220],
        "section_path": block.get("section_path", []),
        "zone_type": "pending_gpt_semantic_judgment",
        "should_fill_text": "pending_gpt_semantic_judgment",
        "script_reason": "structural_fact_only_no_semantic_text_decision",
        "requires_gpt_semantic_review": True,
    }


def main() -> None:
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    structure_path = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "work" / "doc_structure.json"
    output_path = Path(sys.argv[3]) if len(sys.argv) > 3 else workspace / "work" / "draft_text_fill_candidates.json"
    if not structure_path.is_absolute():
        structure_path = workspace / structure_path
    if not output_path.is_absolute():
        output_path = workspace / output_path

    data = read_json(structure_path)
    items = []
    for block in data.get("blocks", []):
        if include_block(block):
            items.append(material_item(len(items) + 1, block))

    write_json(
        output_path,
        {
            "plan_stage": "semantic_materials",
            "candidate_kind": "text_fill_semantic_material",
            "source": str(structure_path),
            "decision_owner": "gpt_codex_semantic_planning",
            "script_decision_policy": "scripts_do_not_decide_text_fill_slots_or_zone_type",
            "requires_gpt_refinement": True,
            "refined_output": str(workspace / "work" / "refined_text_fill_plan.json"),
            "semantic_planning_instructions": [
                "Read work/doc_structure.json as the source of truth.",
                "Classify each planned text edit as answer_area, question_area, reference_material, identity_area, or unknown.",
                "Do not rewrite question_area or reference_material unless the user explicitly asks to edit the question text.",
                "Do not treat long requirement text as answer content.",
                "Only write into answer areas, explicit blanks, table answer cells, or user-approved replacement targets.",
            ],
            "items": items,
        },
    )
    print(output_path)


if __name__ == "__main__":
    main()
