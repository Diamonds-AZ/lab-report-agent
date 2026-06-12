from __future__ import annotations

from pathlib import Path
import argparse
import re
import sys

from utils.file_io import read_text, write_json, write_text
from utils.fs_safety import (
    configure_utf8_stdio,
    copy_template_to_input,
    safe_clean_dir,
)


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def extract_scalar(text: str, key: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(key + ":"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def safe_input_name(source: Path) -> str:
    name = re.sub(r'[<>:"/\\|?*]+', "-", source.name).strip(" .")
    return name or "template.docx"


def assert_inside_workspace(workspace: Path, target: Path) -> None:
    resolved_workspace = workspace.resolve()
    resolved_target = target.resolve()
    if resolved_target != resolved_workspace and resolved_workspace not in resolved_target.parents:
        raise RuntimeError(f"Refusing to modify path outside workspace: {resolved_target}")


def task_yaml_text(
    task_name: str,
    input_report: str,
    experiment_type: str,
    fill_identity_fields: bool,
    output_dir: str,
    workflow_stage: str,
    output_report_name: str | None = None,
    clear_identity_fields: bool = False,
) -> str:
    identity_policy = "fill_identity_fields" if fill_identity_fields else ("clear_identity_fields" if clear_identity_fields else "preserve_existing_identity")
    identity_reason = "当前任务初始化生成；identity_policy 明确区分保留已有、清空已有、填写身份字段。"
    output_name_line = f'output_report_name: "{output_report_name}"\n' if output_report_name else ""
    return f'''task_name: "{task_name}"
input_report: "{input_report}"
{output_name_line}experiment_type: "{experiment_type}"

workflow_stage: "{workflow_stage}"

target_mode: "single"
target_students: []
temporary_students: []

output_dir: "{output_dir}"

execution_mode: "synthetic"
image_generation_model: "gpt-image-2"

requirements:
  analyze_template: true
  fill_text: true
  generate_images: true
  insert_images: true
  preserve_structure: true
  batch_generate: false

identity_rules:
  identity_policy: "{identity_policy}"
  fill_identity_fields: {bool_text(fill_identity_fields)}
  clear_identity_fields: {bool_text(clear_identity_fields)}
  use_identity_in_report: {bool_text(fill_identity_fields)}
  use_identity_in_images: false
  use_identity_in_filename: false
  reason: "{identity_reason}"

semantic_planning:
  use_gpt_text_planner: true
  use_gpt_image_planner: true

image_rules:
  max_merge_count: 4
  platform_must_match_profile: true
  use_reference_images: true
  reference_image_mode: "style_and_layout_only"
  auto_check_images: false
  manual_review_required: true
  regenerate_only_when_user_requests: true
  per_student_images: false
  image_count_policy:
    warn_threshold: 8
    confirm_threshold: 12
    hard_limit: 40

fill_rules:
  fill_blank_in_place: true
  semantic_blank_detection: true
  doc_structure_output: "work/doc_structure.json"
  draft_text_fill_candidates_output: "work/draft_text_fill_candidates.json"
  refined_text_fill_plan_output: "work/refined_text_fill_plan.json"
  blank_fill_audit_output: "work/blank_fill_audit.md"
  forbid_fill_prefix_for_blanks: true
  fill_prefix_forbidden:
    - "填写："
    - "应填入："
    - "答案："

content_overrides:
  writing_style: "像大学生写的，严谨自然，不要太AI"
  principle_length: "short"
  steps_detail_level: "short"
  analysis_length: "short"
  summary_style: "自然简洁"
  avoid_ai_tone: true
'''


def write_startup_audit(workspace: Path, audit: dict) -> None:
    write_json(workspace / "work" / "task_startup_audit.json", audit)
    lines = [
        "# Task Startup Audit",
        "",
        f"- task_name: {audit.get('task_name', '')}",
        f"- input_report: `{audit.get('input_report', '')}`",
        f"- output_report_name: `{audit.get('output_report_name') or ''}`",
        f"- workspace: `{audit.get('workspace', '')}`",
        f"- fill_identity_fields: {audit.get('fill_identity_fields')}",
        f"- clear_identity_fields: {audit.get('clear_identity_fields')}",
        f"- identity_policy: {audit.get('identity_policy') or ''}",
        f"- cleaned_work_dir: {audit.get('cleaned_work_dir')}",
        f"- cleaned_output_reports_dir: {audit.get('cleaned_output_reports_dir')}",
        f"- template_copied_to_input: {audit.get('template_copied_to_input')}",
        f"- template_readonly_removed: {audit.get('template_readonly_removed')}",
        f"- old_task_yaml_detected: {audit.get('old_task_yaml_detected')}",
        f"- old_task_name: {audit.get('old_task_name') or ''}",
        f"- new_task_name: {audit.get('new_task_name')}",
        f"- task_yaml_rewritten: {audit.get('task_yaml_rewritten')}",
        "",
        "## Notes",
        "",
    ]
    for note in audit.get("notes", []):
        lines.append(f"- {note}")
    write_text(workspace / "work" / "task_startup_audit.md", "\n".join(lines) + "\n")


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Prepare an isolated lab-report task workspace.")
    parser.add_argument("workspace")
    parser.add_argument("--source-template", required=True)
    parser.add_argument("--task-name", required=True)
    parser.add_argument("--experiment-type", default="auto")
    parser.add_argument("--output-dir", default="output/reports")
    parser.add_argument("--output-report-name")
    parser.add_argument("--workflow-stage", default="first_run_test")
    parser.add_argument("--fill-identity-fields", action="store_true")
    parser.add_argument("--clear-identity-fields", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    source_template = Path(args.source_template).resolve()
    if not source_template.exists():
        raise FileNotFoundError(f"Input template does not exist: {source_template}")

    work_dir = workspace / "work"
    reports_dir = workspace / args.output_dir
    assert_inside_workspace(workspace, work_dir)
    assert_inside_workspace(workspace, reports_dir)

    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "input").mkdir(parents=True, exist_ok=True)
    (workspace / "configs").mkdir(parents=True, exist_ok=True)

    old_task_path = workspace / "configs" / "task.yaml"
    old_task_text = read_text(old_task_path) if old_task_path.exists() else ""
    old_task_name = extract_scalar(old_task_text, "task_name") if old_task_text else None
    old_input_report = extract_scalar(old_task_text, "input_report") if old_task_text else None

    safe_clean_dir(work_dir, keep_dir=True)
    safe_clean_dir(reports_dir, keep_dir=True)

    input_name = safe_input_name(source_template)
    input_rel = str(Path("input") / input_name).replace("\\", "/")
    copy_info = copy_template_to_input(source_template, workspace / input_rel)

    new_task_text = task_yaml_text(
        task_name=args.task_name,
        input_report=input_rel,
        experiment_type=args.experiment_type,
        fill_identity_fields=args.fill_identity_fields,
        output_dir=args.output_dir,
        workflow_stage=args.workflow_stage,
        output_report_name=args.output_report_name,
        clear_identity_fields=args.clear_identity_fields,
    )
    write_text(old_task_path, new_task_text)

    old_task_yaml_detected = bool(
        old_task_text
        and (
            old_task_name != args.task_name
            or old_input_report != input_rel
        )
    )
    audit = {
        "task_name": args.task_name,
        "new_task_name": args.task_name,
        "input_report": input_rel,
        "output_report_name": args.output_report_name,
        "source_template": str(source_template),
        "workspace": str(workspace),
        "fill_identity_fields": args.fill_identity_fields,
        "clear_identity_fields": args.clear_identity_fields,
        "identity_policy": "fill_identity_fields" if args.fill_identity_fields else ("clear_identity_fields" if args.clear_identity_fields else "preserve_existing_identity"),
        "cleaned_work_dir": True,
        "cleaned_output_reports_dir": True,
        "template_copied_to_input": copy_info["copied"],
        "template_readonly_removed": copy_info["readonly_removed"],
        "template_is_writable": copy_info["is_writable"],
        "old_task_yaml_detected": old_task_yaml_detected,
        "old_task_name": old_task_name,
        "old_input_report": old_input_report,
        "task_yaml_rewritten": True,
        "current_run_id": None,
        "image_output_dir": None,
        "notes": [
            "work/ and output reports were cleaned for this new task.",
            "configs/task.yaml was rewritten only through prepare_new_task.",
        ],
    }
    write_startup_audit(workspace, audit)
    print(workspace / "work" / "task_startup_audit.md")


if __name__ == "__main__":
    main()
