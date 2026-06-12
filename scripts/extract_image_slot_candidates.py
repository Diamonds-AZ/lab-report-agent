from __future__ import annotations

from pathlib import Path
import sys

from utils.file_io import read_json, write_json


def structural_role(block: dict) -> str:
    if block.get("block_type") == "table_cell" and block.get("is_empty"):
        return "empty_table_cell"
    if block.get("is_empty"):
        return "empty_paragraph"
    text = (block.get("text") or "").strip()
    if text and len(text) <= 40 and any(mark in text for mark in ("一、", "二、", "三、", "四、", "1、", "2、", "3、", ": ", "：")):
        return "short_heading_or_prompt"
    return "context_block"


def material_item(idx: int, block: dict) -> dict:
    return {
        "candidate_id": f"image_material_{idx:03d}",
        "block_id": block["block_id"],
        "material_type": "document_structure_fact",
        "structural_role": structural_role(block),
        "block_type": block.get("block_type"),
        "text": block.get("text", ""),
        "is_empty": bool(block.get("is_empty")),
        "table_index": block.get("table_index"),
        "row_index": block.get("row_index"),
        "cell_index": block.get("cell_index"),
        "left_context": (block.get("previous_text") or "")[-220:],
        "right_context": (block.get("next_text") or "")[:220],
        "section_path": block.get("section_path", []),
        "zone_type": "pending_gpt_semantic_judgment",
        "should_insert_image": "pending_gpt_semantic_judgment",
        "script_reason": "structural_fact_only_no_semantic_image_decision",
        "requires_gpt_semantic_review": True,
    }


def include_block(block: dict) -> bool:
    if block.get("block_type") == "table_cell" and block.get("is_empty"):
        return True
    if block.get("is_empty"):
        return True
    text = (block.get("text") or "").strip()
    if not text:
        return False
    if len(text) <= 120:
        return True
    return any(token in text for token in ("实验报告模板", "程序流程图", "实验现象", "实验结果", "截图", "下图", "如下图", "结果展示"))


def main() -> None:
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    structure_path = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "work" / "doc_structure.json"
    output_path = Path(sys.argv[3]) if len(sys.argv) > 3 else workspace / "work" / "draft_image_slot_candidates.json"
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
            "candidate_kind": "image_slot_semantic_material",
            "source": str(structure_path),
            "decision_owner": "gpt_codex_semantic_planning",
            "script_decision_policy": "scripts_do_not_decide_image_slots_or_zone_type",
            "requires_gpt_refinement": True,
            "refined_output": str(workspace / "work" / "refined_image_plan.json"),
            "semantic_planning_instructions": [
                "Read work/doc_structure.json as the source of truth.",
                "Classify every planned image target as answer_area, question_area, reference_material, identity_area, or unknown.",
                "Do not insert images into question_area or reference_material unless the user explicitly asks to modify the question text.",
                "Long requirement text containing words such as 下图 or 如下图 may be reference material, not an answer slot.",
                "Prefer answer areas after labels such as 实验报告模板, 程序流程图, 实验现象, 实验结果展示 when the template separates question text from report-fill areas.",
            ],
            "items": items,
        },
    )
    print(output_path)


if __name__ == "__main__":
    main()
