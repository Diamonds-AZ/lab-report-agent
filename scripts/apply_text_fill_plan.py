from collections import defaultdict
from pathlib import Path
import os
import re
import shutil
import sys

from docx import Document

from utils.file_io import read_json, write_text
from utils.fs_safety import assert_output_path_writable, configure_utf8_stdio, make_writable


SPACE_RE = re.compile(r" {2,}|\t+")
PLACEHOLDER_RE = re.compile(r"_{3,}|\(\s*\)|（\s*）|【(?:待填写(?::|：)?.*?)?】")
FORBIDDEN_ANSWER_PREFIXES = ("填写：", "应填入：", "答案：")


def path_from_env(name, default):
    return Path(os.environ.get(name, default))


ROOT = Path(__file__).resolve().parents[1]
INPUT_DOCX = path_from_env("LAB_REPORT_INPUT", ROOT / "input" / "template.docx")
STRUCTURE = path_from_env("LAB_REPORT_STRUCTURE", ROOT / "work" / "doc_structure.json")
TEXT_PLAN = path_from_env("LAB_REPORT_TEXT_PLAN", ROOT / "work" / "refined_text_fill_plan.json")
OUTPUT_DOCX = path_from_env("LAB_REPORT_OUTPUT", ROOT / "output" / "reports" / "流程测试_实验报告.docx")
AUDIT = path_from_env("LAB_REPORT_AUDIT", ROOT / "work" / "text_fill_audit.md")


def block_lookup():
    data = read_json(STRUCTURE)
    return {block["block_id"]: block for block in data["blocks"]}


def locate_block(doc, block_id):
    if block_id.startswith("p"):
        return ("paragraph", doc.paragraphs[int(block_id[1:])])
    match = re.fullmatch(r"t(\d+)_r(\d+)_c(\d+)", block_id)
    if match:
        table_idx, row_idx, cell_idx = map(int, match.groups())
        return ("table_cell", doc.tables[table_idx].rows[row_idx].cells[cell_idx])
    raise ValueError(f"Unsupported block_id: {block_id}")


def validate_plan(plan):
    if plan.get("plan_stage") != "refined":
        raise RuntimeError("refined_text_fill_plan.json must set plan_stage='refined'.")
    if plan.get("source_stage") != "gpt_semantic_planning":
        raise RuntimeError("refined_text_fill_plan.json must set source_stage='gpt_semantic_planning'.")
    if plan.get("source_stage") == "draft_copy":
        raise RuntimeError("refined_text_fill_plan.json must not be a copied or renamed draft file.")
    for item in plan.get("items", []):
        if not item.get("is_text_fill", True):
            continue
        for key in ("item_id", "block_id", "slot_index", "left_context", "right_context", "answer", "replacement_strategy", "confidence", "reason"):
            if key not in item:
                raise RuntimeError(f"Text fill item missing required field {key}: {item}")
        if str(item.get("answer", "")).startswith(FORBIDDEN_ANSWER_PREFIXES):
            raise RuntimeError(f"{item['item_id']} uses forbidden answer prefix.")


def patterns_for_strategy(strategy):
    if strategy == "replace_placeholder":
        return [PLACEHOLDER_RE]
    if strategy == "replace_blank_spaces":
        return [SPACE_RE]
    if strategy == "fill_after_prefix":
        return [PLACEHOLDER_RE, SPACE_RE]
    raise RuntimeError(f"Unsupported in-place strategy: {strategy}")


def replace_blank_occurrence(paragraph, answer, strategy, occurrence_index=0):
    if occurrence_index < 0:
        raise RuntimeError(f"Invalid occurrence_index: {occurrence_index}")
    seen = 0
    patterns = patterns_for_strategy(strategy)
    for run in paragraph.runs:
        text = run.text or ""
        for pattern in patterns:
            for match in pattern.finditer(text):
                if seen == occurrence_index:
                    run.text = text[: match.start()] + answer + text[match.end() :]
                    run.underline = True
                    return occurrence_index
                seen += 1
    raise RuntimeError(f"No in-place blank target found at occurrence_index={occurrence_index}; refusing to append answer.")


def apply_to_paragraph(paragraph, answer, strategy, occurrence_index=0):
    replaced_occurrence = replace_blank_occurrence(paragraph, answer, strategy, occurrence_index)
    if replaced_occurrence is None:
        raise RuntimeError("No in-place blank target found; refusing to append answer.")
    return paragraph.text, replaced_occurrence


def apply_to_cell(cell, answer, strategy, occurrence_index=0):
    if strategy == "fill_table_cell":
        if cell.text.strip():
            raise RuntimeError("Target table cell is not empty; refusing non-in-place fill.")
        cell.text = answer
        return cell.text, 0
    if strategy == "replace_cell_content":
        cell.text = answer
        return cell.text, 0
    if not cell.paragraphs:
        raise RuntimeError("Target cell has no paragraph for in-place fill.")
    return apply_to_paragraph(cell.paragraphs[0], answer, strategy, occurrence_index)


def doc_all_text(doc):
    return "\n".join(
        [p.text for p in doc.paragraphs]
        + [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
    )


def main():
    configure_utf8_stdio()
    if not TEXT_PLAN.exists():
        message = "ACTION_REQUIRED: work/refined_text_fill_plan.json is missing. Codex/GPT must create it from doc_structure and draft_text_fill_candidates."
        write_text(AUDIT, "# Text Fill Audit\n\n" + message + "\n")
        print(message)
        raise SystemExit(2)

    plan = read_json(TEXT_PLAN)
    validate_plan(plan)

    assert_output_path_writable(OUTPUT_DOCX)
    shutil.copy2(INPUT_DOCX, OUTPUT_DOCX)
    make_writable(OUTPUT_DOCX)
    assert_output_path_writable(OUTPUT_DOCX)
    doc = Document(OUTPUT_DOCX)
    blocks = block_lookup()
    grouped = defaultdict(list)
    unresolved = list(plan.get("unresolved", []))
    skipped = []

    for item in plan.get("items", []):
        if not item.get("is_text_fill", True):
            skipped.append(item)
            continue
        if item.get("confidence") == "low" or item.get("need_user_review"):
            unresolved.append({"item": item, "reason": "low confidence or user review required"})
            continue
        grouped[item["block_id"]].append(item)

    applied = []
    for block_id, items in grouped.items():
        block = blocks.get(block_id)
        if not block:
            unresolved.extend({"item": item, "reason": "block_id not found"} for item in items)
            continue
        target_kind, target = locate_block(doc, block_id)
        before = block.get("text", "")
        for item in sorted(items, key=lambda x: int(x.get("occurrence_index", x.get("slot_index", 0)) or 0), reverse=True):
            answer = item.get("answer", "")
            strategy = item.get("replacement_strategy", "replace_blank_spaces")
            occurrence_index = int(item.get("occurrence_index", item.get("slot_index", 0)) or 0)
            try:
                if target_kind == "paragraph":
                    after, replaced_occurrence = apply_to_paragraph(target, answer, strategy, occurrence_index)
                else:
                    after, replaced_occurrence = apply_to_cell(target, answer, strategy, occurrence_index)
                applied.append(
                    {
                        "item_id": item["item_id"],
                        "block_id": block_id,
                        "strategy": strategy,
                        "answer": answer,
                        "requested_occurrence_index": occurrence_index,
                        "replaced_occurrence_index": replaced_occurrence,
                        "before": before,
                        "after": after,
                    }
                )
            except Exception as exc:
                unresolved.append(
                    {
                        "item_id": item.get("item_id"),
                        "block_id": block_id,
                        "reason": str(exc),
                        "unsupported_or_unmatched_strategy": strategy,
                        "requested_occurrence_index": occurrence_index,
                    }
                )
                continue

    assert_output_path_writable(OUTPUT_DOCX)
    doc.save(OUTPUT_DOCX)
    reloaded = Document(OUTPUT_DOCX)
    all_text = doc_all_text(reloaded)
    forbidden = []
    for item in applied:
        answer = str(item.get("answer", ""))
        forbidden.extend(prefix for prefix in FORBIDDEN_ANSWER_PREFIXES if answer.startswith(prefix))
    lines = [
        "# Text Fill Audit",
        "",
        f"- refined_text_fill_plan: `{TEXT_PLAN}`",
        f"- applied_count: {len(applied)}",
        f"- unresolved_count: {len(unresolved)}",
        f"- forbidden_prefixes: {', '.join(forbidden) if forbidden else 'none'}",
        "",
        "## Applied",
        "",
        "| item_id | block_id | strategy | occurrence | answer |",
        "|---|---|---|---:|---|",
    ]
    for item in applied:
        lines.append(f"| {item['item_id']} | {item['block_id']} | {item['strategy']} | {item['replaced_occurrence_index']} | {item['answer']} |")
    if unresolved:
        lines.extend(["", "## Unresolved", ""])
        for item in unresolved:
            lines.append(f"- {item}")
    write_text(AUDIT, "\n".join(lines) + "\n")
    write_text(AUDIT.parent / "blank_fill_audit.md", "\n".join(lines) + "\n")
    print(OUTPUT_DOCX)
    print(AUDIT)


if __name__ == "__main__":
    main()
