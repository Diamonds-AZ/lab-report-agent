from pathlib import Path
from collections import Counter
import json
import re
import sys

from docx import Document
from utils.file_io import read_json, write_json, write_text
from utils.fs_safety import configure_utf8_stdio
from utils.confirmation import valid_confirmation_source, confirmation_reason


FORBIDDEN_PREFIXES = ("填写：", "应填入：", "答案：")
IDENTITY_SAMPLES = ("张三", "李四", "20240001", "20240002")


def doc_text(doc):
    return "\n".join([p.text for p in doc.paragraphs] + [cell.text for table in doc.tables for row in table.rows for cell in row.cells])


def table_has_image(table):
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    if run._element.xpath(".//a:blip"):
                        return True
    return False


def empty_tables(doc):
    return [idx for idx, table in enumerate(doc.tables) if not "".join(cell.text.strip() for row in table.rows for cell in row.cells) and not table_has_image(table)]


def paragraph_index(block_id):
    match = re.fullmatch(r"p(\d+)", str(block_id or ""))
    return int(match.group(1)) if match else None


def image_blank_paragraph_indexes(workspace):
    current_path = workspace / "work" / "current_run.json"
    if not current_path.exists():
        return set()
    current = read_json(current_path)
    insert_audit_path = Path(current.get("run_dir", "")) / "image_insert_audit.json"
    if not insert_audit_path.exists():
        return set()
    insert_audit = read_json(insert_audit_path)
    ignored = set()
    image_items = insert_audit.get("unresolved_image", []) + insert_audit.get("inserted", [])
    for item in image_items:
        if item.get("layout_type") != "paragraph_blank_region":
            continue
        block_range = item.get("target_block_range") or []
        if len(block_range) != 2:
            continue
        start = paragraph_index(block_range[0])
        end = paragraph_index(block_range[1])
        if start is None or end is None or start > end:
            continue
        ignored.update(range(start, end + 1))
    return ignored


def underlined_blank_runs(doc, ignored_paragraph_indexes=None):
    ignored_paragraph_indexes = ignored_paragraph_indexes or set()
    total = 0
    for idx, paragraph in enumerate(doc.paragraphs):
        if idx in ignored_paragraph_indexes:
            continue
        for run in paragraph.runs:
            if run.underline and re.fullmatch(r"\s{3,}", run.text or ""):
                total += 1
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        if run.underline and re.fullmatch(r"\s{3,}", run.text or ""):
                            total += 1
    return total


def input_report_path(workspace):
    context = workspace / "work" / "current_task_context.json"
    if context.exists():
        return Path(read_json(context).get("input_report", ""))
    structure = workspace / "work" / "doc_structure.json"
    if structure.exists():
        return Path(read_json(structure).get("input_report", ""))
    return None


def encoding_counts(path):
    if not path or not path.exists():
        return {"triple_question_mark_count": 0, "replacement_char_count": 0}
    text = doc_text(Document(path))
    return {"triple_question_mark_count": text.count("???"), "replacement_char_count": text.count("\ufffd")}


def image_audit(workspace):
    current_path = workspace / "work" / "current_run.json"
    plan_path = workspace / "work" / "image_generation_plan.json"
    current = read_json(current_path) if current_path.exists() else {}
    plan = read_json(plan_path) if plan_path.exists() else {}
    run_id_consistent = bool(current and plan and current.get("run_id") == plan.get("run_id"))
    generated_dir_value = plan.get("generated_images_dir", "") if plan else ""
    generated_dir = Path(generated_dir_value) if generated_dir_value else None
    generated_image_count = 0
    missing_images = []
    unexpected_images = []
    image_source_summary = Counter(
        item.get("image_source", "unknown") or "unknown"
        for item in plan.get("items", [])
    )
    if generated_dir and generated_dir.exists():
        generated_files = sorted(p.name for p in generated_dir.glob("*.png") if p.is_file())
        expected_files = [item.get("output_filename") for item in plan.get("items", []) if item.get("output_filename")]
        missing_images = [name for name in expected_files if name not in generated_files]
        unexpected_images = [name for name in generated_files if name not in set(expected_files)]
        generated_image_count = len(expected_files) - len(missing_images)
    elif plan.get("items"):
        missing_images = [item.get("output_filename") for item in plan.get("items", []) if item.get("output_filename")]
    insert_audit_path = Path(current.get("run_dir", "")) / "image_insert_audit.json" if current else None
    insert_audit = read_json(insert_audit_path) if insert_audit_path and insert_audit_path.exists() else {}
    quality_audit_path = Path(current.get("run_dir", "")) / "image_quality_audit.json" if current else None
    quality_audit = read_json(quality_audit_path) if quality_audit_path and quality_audit_path.exists() else {}
    if insert_audit.get("missing_images"):
        missing_images = [item.get("output_filename") for item in insert_audit.get("missing_images", [])]
    if insert_audit.get("unexpected_images"):
        unexpected_images = insert_audit.get("unexpected_images", [])
    cropped = insert_audit.get("suspected_cropped_images", [])
    layout_warnings = insert_audit.get("image_layout_warnings", [])
    quality_warnings = insert_audit.get("image_quality_warnings") or quality_audit.get("warnings", [])
    return {
        "run_id": current.get("run_id"),
        "run_id_consistent": run_id_consistent,
        "generated_images_dir": str(generated_dir) if generated_dir else "",
        "expected_image_count": plan.get("expected_image_count", 0),
        "generated_image_count": generated_image_count,
        "inserted_image_count": len(insert_audit.get("inserted", [])),
        "unresolved_image_insert_count": len(insert_audit.get("unresolved_image", [])),
        "unresolved_image_insert": insert_audit.get("unresolved_image", []),
        "legacy_image_used": bool(insert_audit.get("legacy_image_used", False)),
        "missing_images": missing_images,
        "unexpected_images": unexpected_images,
        "suspected_cropped_images": len(cropped),
        "suspected_cropped_image_items": cropped,
        "image_layout_warnings": layout_warnings,
        "image_quality_warning_count": len(quality_warnings),
        "image_quality_warnings": quality_warnings,
        "image_source_summary": dict(sorted(image_source_summary.items())),
    }


def plan_fingerprint(plan):
    import hashlib

    parts = [str(plan.get("run_id", "")), str(plan.get("expected_image_count", 0))]
    for item in plan.get("items", []):
        parts.append(str(item.get("image_id", "")))
        parts.append(str(item.get("output_filename", "")))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def confirmation_audit(workspace):
    context_path = workspace / "work" / "current_task_context.json"
    plan_path = workspace / "work" / "image_generation_plan.json"
    current_path = workspace / "work" / "current_run.json"
    confirmation_path = workspace / "work" / "image_count_confirmation.json"
    context = read_json(context_path) if context_path.exists() else {}
    plan = read_json(plan_path) if plan_path.exists() else {}
    current = read_json(current_path) if current_path.exists() else {}
    policy = context.get("image_count_policy") or {}
    count = int(plan.get("expected_image_count", 0) or 0)
    threshold = int(policy.get("confirm_threshold", 12))
    required = count > threshold
    result = {
        "image_count_confirmation_required": required,
        "image_count_confirmation_valid": not required,
        "image_count_confirmation_reason": "not_required" if not required else "missing_confirmation_file",
    }
    if not required:
        return result
    if not confirmation_path.exists():
        return result
    confirmation = read_json(confirmation_path)
    confirmed_input = str(confirmation.get("input_report", ""))
    context_input = str(context.get("input_report", ""))
    input_matches = (
        not confirmed_input
        or confirmed_input == context_input
        or context_input.endswith(confirmed_input.replace("/", "\\"))
        or Path(context_input).name == Path(confirmed_input).name
    )
    checks = [
        (confirmation.get("confirmed") is True, "confirmed_not_true"),
        (confirmation.get("run_id") == current.get("run_id") == plan.get("run_id"), "run_id_mismatch"),
        (int(confirmation.get("expected_image_count", -1)) == count, "expected_image_count_mismatch"),
        (int(confirmation.get("confirm_threshold", -1)) == threshold, "confirm_threshold_mismatch"),
        (input_matches, "input_report_mismatch"),
        ((not confirmation.get("plan_fingerprint")) or confirmation.get("plan_fingerprint") == plan_fingerprint(plan), "plan_fingerprint_mismatch"),
    ]
    failed = [reason for ok, reason in checks if not ok]
    result["image_count_confirmation_valid"] = not failed
    result["image_count_confirmation_reason"] = "confirmed" if not failed else failed[0]
    return result


def task_confirmation_audit(workspace):
    path = workspace / "work" / "task_directives.json"
    result = {
        "task_directives_confirmed": False,
        "task_directives_reason": "missing_task_directives",
        "experiment_type": "",
        "document_pattern": "",
        "writing_mode": "",
    }
    if not path.exists():
        return result
    data = read_json(path)
    result["task_directives_confirmed"] = valid_confirmation_source(data)
    result["task_directives_reason"] = confirmation_reason(data)
    result["task_confirmation_source"] = data.get("confirmation_source", "")
    mode = data.get("confirmation_mode")
    result["task_confirmation_mode"] = mode.get("value", "") if isinstance(mode, dict) else (mode or "")
    result["experiment_type"] = (data.get("experiment_type") or {}).get("value", "")
    result["document_pattern"] = (data.get("document_pattern") or {}).get("value", "")
    result["writing_mode"] = (data.get("writing_mode") or {}).get("value", "")
    result["image_mode"] = (data.get("image_mode") or {}).get("value", "")
    return result


def image_plan_confirmation_audit(workspace):
    path = workspace / "work" / "refined_image_plan.json"
    if not path.exists():
        return {"image_plan_confirmed": True, "image_plan_confirmation_reason": "no_image_plan"}
    data = read_json(path)
    has_required = any(item.get("is_image_required") for item in data.get("items", []))
    if not has_required:
        return {"image_plan_confirmed": True, "image_plan_confirmation_reason": "no_required_images"}
    confirmation_doc = workspace / "work" / "image_insertion_confirmation.md"
    confirmation_doc_exists = confirmation_doc.exists()
    confirmation_doc_complete = False
    if confirmation_doc_exists:
        text = confirmation_doc.read_text(encoding="utf-8-sig", errors="replace")
        confirmation_doc_complete = all(marker in text for marker in ("| 图片", "区域类型", "插入位置", "附近文字/锚点"))
    confirmed = valid_confirmation_source(data)
    mode = data.get("confirmation_mode")
    return {
        "image_plan_confirmed": confirmed and confirmation_doc_complete,
        "image_plan_confirmation_reason": confirmation_reason(data) if confirmation_doc_complete else "missing_or_incomplete_image_insertion_confirmation_md",
        "image_plan_confirmation_source": data.get("confirmation_source", ""),
        "image_plan_confirmation_mode": mode.get("value", "") if isinstance(mode, dict) else (mode or ""),
        "image_insertion_confirmation_md_exists": confirmation_doc_exists,
        "image_insertion_confirmation_md_complete": confirmation_doc_complete,
    }


def manifest_audit(workspace):
    path = workspace / "work" / "generated_images_manifest_audit.json"
    if not path.exists():
        return {
            "generated_images_manifest_valid": False,
            "generated_images_manifest_required_gpt_image_2_only": False,
            "generated_images_manifest_failures": ["missing_manifest_audit"],
        }
    data = read_json(path)
    return {
        "generated_images_manifest_valid": data.get("valid") is True,
        "generated_images_manifest_required_gpt_image_2_only": data.get("required_gpt_image_2_only") is True,
        "generated_images_manifest_failures": data.get("failures", []),
    }


def requirement_coverage_audit(workspace):
    path = workspace / "work" / "requirement_coverage_report.json"
    if not path.exists():
        return {
            "real_missing_requirement_count": 0,
            "real_missing_requirement": [],
            "requirement_count": 0,
        }
    data = read_json(path)
    return {
        "real_missing_requirement_count": int(data.get("real_missing_requirement_count", 0) or 0),
        "real_missing_requirement": data.get("real_missing_requirement", []),
        "requirement_count": int(data.get("requirement_count", 0) or 0),
    }


def unresolved_counts(workspace):
    text_plan = workspace / "work" / "refined_text_fill_plan.json"
    image_plan = workspace / "work" / "refined_image_plan.json"
    text_unresolved = len(read_json(text_plan).get("unresolved", [])) if text_plan.exists() else None
    image_unresolved = len(read_json(image_plan).get("unresolved", [])) if image_plan.exists() else None
    return text_unresolved, image_unresolved


def classify_unresolved_text_item(item):
    text = json.dumps(item, ensure_ascii=False).lower()
    identity_terms = (
        "姓名",
        "学号",
        "班级",
        "专业",
        "年级",
        "identity",
        "student id",
        "name",
    )
    unchanged_terms = (
        "模板原文已经完整",
        "已经完整",
        "不需要改写",
        "不需要处理",
        "排版",
        "图片区域",
        "image",
        "screenshot",
        "blank region",
        "paragraph_blank_region",
        "用户明确要求不处理",
    )
    real_terms = (
        "其结果为",
        "原因是",
        "请补充完整命令",
        "完整命令",
        "命令空格",
        "正文",
        "答案",
        "未填写",
        "漏填",
    )
    if any(term.lower() in text for term in identity_terms):
        return "expected_blank"
    if any(term.lower() in text for term in unchanged_terms):
        return "intentionally_unchanged"
    if any(term.lower() in text for term in real_terms):
        return "real_unresolved"
    return "real_unresolved"


def classify_unresolved_text(workspace, document_text=""):
    text_plan = workspace / "work" / "refined_text_fill_plan.json"
    details = {
        "expected_blank": [],
        "intentionally_unchanged": [],
        "real_unresolved": [],
    }
    if text_plan.exists():
        for item in read_json(text_plan).get("unresolved", []):
            category = classify_unresolved_text_item(item)
            details[category].append(item)

    real_patterns = [
        r"其结果为\s*(?:$|\n)",
        r"原因是\s*(?:$|\n)",
        r"请补充完整命令\s*(?:$|\n)",
    ]
    existing_real = json.dumps(details["real_unresolved"], ensure_ascii=False)
    for pattern in real_patterns:
        marker = re.sub(r"\\s.*", "", pattern)
        if re.search(pattern, document_text) and marker not in existing_real:
            details["real_unresolved"].append({"reason": "document_text_pattern", "pattern": pattern})

    return {
        "expected_blank_count": len(details["expected_blank"]),
        "intentionally_unchanged_count": len(details["intentionally_unchanged"]),
        "real_unresolved_text_count": len(details["real_unresolved"]),
        "unresolved_text_details": details,
    }


def forbidden_answer_prefixes(workspace):
    text_plan = workspace / "work" / "refined_text_fill_plan.json"
    if not text_plan.exists():
        return []
    plan = read_json(text_plan)
    bad = []
    for item in plan.get("items", []):
        answer = str(item.get("answer", ""))
        bad.extend(prefix for prefix in FORBIDDEN_PREFIXES if answer.startswith(prefix))
    return sorted(set(bad))


def inspect(workspace, report):
    doc = Document(report)
    text = doc_text(doc)
    input_counts = encoding_counts(input_report_path(workspace))
    output_counts = {"triple_question_mark_count": text.count("???"), "replacement_char_count": text.count("\ufffd")}
    encoding_pollution = (
        output_counts["triple_question_mark_count"] > input_counts["triple_question_mark_count"]
        or output_counts["replacement_char_count"] > input_counts["replacement_char_count"]
    )
    img = image_audit(workspace)
    confirmation = confirmation_audit(workspace)
    task_confirmation = task_confirmation_audit(workspace)
    image_plan_confirmation = image_plan_confirmation_audit(workspace)
    manifest = manifest_audit(workspace)
    requirement_coverage = requirement_coverage_audit(workspace)
    text_unresolved, image_unresolved = unresolved_counts(workspace)
    unresolved_text = classify_unresolved_text(workspace, text)
    empty = empty_tables(doc)
    ignored_image_blanks = image_blank_paragraph_indexes(workspace)
    bad_prefixes = forbidden_answer_prefixes(workspace)
    unresolved_blank_count = len(re.findall(r"_{3,}", text)) + underlined_blank_runs(doc, ignored_image_blanks)
    hard_fail_reasons = []
    if img["expected_image_count"] and img["generated_image_count"] != img["expected_image_count"]:
        hard_fail_reasons.append("generated_image_count_mismatch")
    if not task_confirmation["task_directives_confirmed"]:
        hard_fail_reasons.append("task_directives_not_confirmed")
    if not image_plan_confirmation["image_plan_confirmed"]:
        hard_fail_reasons.append("image_plan_not_confirmed")
    if manifest["generated_images_manifest_required_gpt_image_2_only"] and not manifest["generated_images_manifest_valid"]:
        hard_fail_reasons.append("unverified_image_source")
    if requirement_coverage["real_missing_requirement_count"]:
        hard_fail_reasons.append("real_missing_requirement")
    if img["missing_images"]:
        hard_fail_reasons.append("missing_images")
    if img["expected_image_count"] and (img["inserted_image_count"] + img["unresolved_image_insert_count"]) not in (0, img["expected_image_count"]):
        hard_fail_reasons.append("inserted_image_count_mismatch")
    if img["legacy_image_used"]:
        hard_fail_reasons.append("legacy_image_used")
    if img["expected_image_count"] and not img["run_id_consistent"]:
        hard_fail_reasons.append("run_id_inconsistent")
    if confirmation["image_count_confirmation_required"] and not confirmation["image_count_confirmation_valid"]:
        hard_fail_reasons.append("image_count_confirmation_invalid")
    if img["suspected_cropped_images"]:
        hard_fail_reasons.append("suspected_cropped_images")
    if encoding_pollution:
        hard_fail_reasons.append("encoding_pollution_detected")
    if bad_prefixes:
        hard_fail_reasons.append("bad_prefix_found")
    if unresolved_blank_count and text_unresolved in (None, 0) and not img["unresolved_image_insert_count"]:
        hard_fail_reasons.append("unresolved_blank_without_plan_record")
    if unresolved_text["real_unresolved_text_count"]:
        hard_fail_reasons.append("real_unresolved_text")
    if empty and image_unresolved in (None, 0) and img["expected_image_count"]:
        hard_fail_reasons.append("empty_image_slots_without_unresolved_record")
    return {
        "report": str(report),
        "exists": report.exists(),
        "empty_image_slots": empty,
        "inline_shapes": len(doc.inline_shapes),
        "input_triple_question_mark_count": input_counts["triple_question_mark_count"],
        "output_triple_question_mark_count": output_counts["triple_question_mark_count"],
        "input_replacement_char_count": input_counts["replacement_char_count"],
        "output_replacement_char_count": output_counts["replacement_char_count"],
        "encoding_pollution_detected": encoding_pollution,
        "unresolved_blank_count": unresolved_blank_count,
        "unresolved_text_fill_count": text_unresolved,
        **unresolved_text,
        "unresolved_image_count": image_unresolved,
        "bad_prefix_found": bool(bad_prefixes),
        "bad_prefixes": bad_prefixes,
        "identity_samples_found": [x for x in IDENTITY_SAMPLES if x in text],
        **img,
        **confirmation,
        **task_confirmation,
        **image_plan_confirmation,
        **manifest,
        **requirement_coverage,
        "hard_fail": bool(hard_fail_reasons),
        "hard_fail_reasons": hard_fail_reasons,
    }


def main():
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    if len(sys.argv) > 2:
        reports = [Path(sys.argv[2])]
    else:
        reports = sorted((workspace / "output" / "reports").glob("*.docx"))
    results = [inspect(workspace, report if report.is_absolute() else workspace / report) for report in reports if report.exists()]
    context_path = workspace / "work" / "current_task_context.json"
    context = read_json(context_path) if context_path.exists() else {}
    lines = ["# Batch Check Report", "", f"- report_count: {len(results)}", ""]
    for item in results:
        final_status = "FAIL" if item["hard_fail"] else "PASS"
        if item["image_count_confirmation_required"] and not item["image_count_confirmation_valid"]:
            final_status = "ACTION_REQUIRED"
        lines.extend(
            [
                "## Summary",
                "",
                f"- final_status: {final_status}",
                f"- hard_fail: {item['hard_fail']}",
                f"- hard_fail_reasons: {json.dumps(item['hard_fail_reasons'], ensure_ascii=False)}",
                f"- output_report: `{item['report']}`",
                f"- run_id: {item.get('run_id') or ''}",
                f"- task_name: {context.get('task_name', '')}",
                f"- resolved_experiment_type: {item.get('experiment_type') or context.get('resolved_experiment_type', '')}",
                f"- task_directives_confirmed: {item.get('task_directives_confirmed')}",
                f"- task_confirmation_mode: {item.get('task_confirmation_mode', '')}",
                f"- task_confirmation_source: {item.get('task_confirmation_source', '')}",
                f"- task_directives_reason: {item.get('task_directives_reason', '')}",
                f"- experiment_type: {item.get('experiment_type', '')}",
                f"- document_pattern: {item.get('document_pattern', '')}",
                f"- writing_mode: {item.get('writing_mode', '')}",
                "",
                "## Images",
                "",
                f"- expected_images: {item['expected_image_count']}",
                f"- generated_images: {item['generated_image_count']}",
                f"- inserted_images: {item['inserted_image_count']}",
                f"- missing_images: {json.dumps(item['missing_images'], ensure_ascii=False)}",
                f"- unexpected_images: {json.dumps(item['unexpected_images'], ensure_ascii=False)}",
                f"- legacy_image_used: {item['legacy_image_used']}",
                f"- image_source_summary: {json.dumps(item['image_source_summary'], ensure_ascii=False)}",
                f"- generated_images_manifest_valid: {item.get('generated_images_manifest_valid')}",
                f"- image_plan_confirmed: {item.get('image_plan_confirmed')}",
                f"- image_plan_confirmation_mode: {item.get('image_plan_confirmation_mode', '')}",
                f"- image_plan_confirmation_source: {item.get('image_plan_confirmation_source', '')}",
                f"- image_plan_confirmation_reason: {item.get('image_plan_confirmation_reason', '')}",
                f"- generated_images_manifest_failures: {json.dumps(item.get('generated_images_manifest_failures', []), ensure_ascii=False)}",
                f"- suspected_cropped_images: {item['suspected_cropped_images']}",
                f"- image_quality_warnings: {item['image_quality_warning_count']}",
                "",
                "## Text",
                "",
                f"- expected_blank_count: {item['expected_blank_count']}",
                f"- intentionally_unchanged_count: {item['intentionally_unchanged_count']}",
                f"- real_unresolved_text_count: {item['real_unresolved_text_count']}",
                f"- unresolved_text_details: {json.dumps(item['unresolved_text_details'], ensure_ascii=False)}",
                f"- requirement_count: {item.get('requirement_count', 0)}",
                f"- real_missing_requirement_count: {item.get('real_missing_requirement_count', 0)}",
                f"- real_missing_requirement: {json.dumps(item.get('real_missing_requirement', []), ensure_ascii=False)}",
                "",
                "## Encoding",
                "",
                f"- encoding_pollution: {item['encoding_pollution_detected']}",
                f"- input ??? count: {item['input_triple_question_mark_count']}",
                f"- output ??? count: {item['output_triple_question_mark_count']}",
                f"- input replacement char count: {item['input_replacement_char_count']}",
                f"- output replacement char count: {item['output_replacement_char_count']}",
                "",
                "## User Actions",
                "",
            ]
        )
        actions = []
        if item["image_quality_warning_count"]:
            actions.append("人工检查图片质量。")
        if item["expected_blank_count"]:
            actions.append("身份字段按策略保留空白，如需填写请重新初始化任务并明确允许身份字段。")
        if item["image_count_confirmation_required"] and not item["image_count_confirmation_valid"]:
            actions.append("确认高数量图片后再继续。")
        if item["real_unresolved_text_count"]:
            actions.append("补齐正文中真实未处理的文本空白。")
        if not item.get("task_directives_confirmed"):
            actions.append("确认第一阶段任务理解。")
        if not item.get("image_plan_confirmed"):
            actions.append("确认第二阶段图片插入计划。")
        if item.get("generated_images_manifest_required_gpt_image_2_only") and not item.get("generated_images_manifest_valid"):
            actions.append("按 image-2 要求重新生成图片并写入 manifest。")
        if item.get("real_missing_requirement_count"):
            actions.append("补齐未覆盖的编号任务。")
        if not actions:
            actions.append("无必须处理事项；仍建议人工快速检查图片和文字一致性。")
        lines.extend(f"- {action}" for action in actions)
        lines.append("")
    write_text(workspace / "work" / "batch_check_report.md", "\n".join(lines) + "\n")
    write_json(workspace / "work" / "batch_check_report.json", results)
    if any(item["hard_fail"] for item in results):
        print(workspace / "work" / "batch_check_report.md")
        raise SystemExit("Hard fail detected; see batch_check_report.json")
    print(workspace / "work" / "batch_check_report.md")


if __name__ == "__main__":
    main()
