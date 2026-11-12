from pathlib import Path
from datetime import datetime
import hashlib
import locale
import os
import re
import subprocess
import sys

from utils.file_io import read_json, read_text, write_json, write_text
from utils.fs_safety import configure_utf8_stdio
from utils.confirmation import valid_confirmation_source


def run(script: Path, *args, check=True):
    cmd = [sys.executable, str(script), *map(str, args)]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    if check and proc.returncode != 0:
        raise RuntimeError(f"{script.name} failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return proc


def _extract_scalar(text: str, key: str):
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(key + ":"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def _section_lines(text: str, section: str):
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


def _extract_nested_scalar(text: str, section: str, key: str):
    for line in _section_lines(text, section):
        stripped = line.strip()
        if stripped.startswith(key + ":"):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def _extract_nested_bool(text: str, section: str, key: str):
    return (_extract_nested_scalar(text, section, key) or "").lower() == "true"


def _extract_image_count_policy(text: str):
    return {
        "warn_threshold": int(_extract_nested_scalar(text, "image_count_policy", "warn_threshold") or 8),
        "confirm_threshold": int(_extract_nested_scalar(text, "image_count_policy", "confirm_threshold") or 12),
        "hard_limit": int(_extract_nested_scalar(text, "image_count_policy", "hard_limit") or 40),
    }


def read_task(workspace: Path):
    path = workspace / "configs" / "task.yaml"
    text = read_text(path) if path.exists() else ""
    return {
        "task_name": _extract_scalar(text, "task_name") or "实验报告",
        "output_report_name": _extract_scalar(text, "output_report_name"),
        "experiment_type": _extract_scalar(text, "experiment_type") or "auto",
        "generate_images": "generate_images: true" in text,
        "insert_images": "insert_images: true" in text,
        "fill_text": "fill_text: true" in text,
        "batch_generate": "batch_generate: true" in text,
        "input_report": _extract_scalar(text, "input_report") or "input/template.docx",
        "output_dir": _extract_scalar(text, "output_dir") or "output/reports",
        "workflow_stage": _extract_scalar(text, "workflow_stage") or "first_run_test",
        "fill_identity_fields": _extract_nested_bool(text, "identity_rules", "fill_identity_fields"),
        "clear_identity_fields": _extract_nested_bool(text, "identity_rules", "clear_identity_fields"),
        "identity_policy": _extract_nested_scalar(text, "identity_rules", "identity_policy"),
        "use_identity_in_report": _extract_nested_bool(text, "identity_rules", "use_identity_in_report"),
        "use_identity_in_images": _extract_nested_scalar(text, "identity_rules", "use_identity_in_images") or "false",
        "per_student_images": _extract_nested_scalar(text, "image_rules", "per_student_images") or "false",
        "use_gpt_text_planner": (_extract_nested_scalar(text, "semantic_planning", "use_gpt_text_planner") or "true").lower() != "false",
        "use_gpt_image_planner": (_extract_nested_scalar(text, "semantic_planning", "use_gpt_image_planner") or "true").lower() != "false",
        "image_count_policy": _extract_image_count_policy(text),
    }


def write_audit(workspace: Path, entries):
    lines = ["# Task Run Audit", "", "| Stage | Status | Detail |", "|---|---|---|"]
    for entry in entries:
        lines.append(f"| {entry['stage']} | {entry['status']} | {entry['detail']} |")
    out = workspace / "work" / "task_run_audit.md"
    write_text(out, "\n".join(lines) + "\n")
    return out


def pending_user_feedback(workspace: Path):
    path = workspace / "work" / "latest_user_feedback.json"
    if not path.exists():
        return None
    try:
        feedback = read_json(path)
    except Exception:
        return None
    return feedback if feedback.get("status") == "pending_revision" else None


def image_plan_fingerprint(plan):
    parts = [str(plan.get("run_id", "")), str(plan.get("expected_image_count", 0))]
    for item in plan.get("items", []):
        parts.append(str(item.get("image_id", "")))
        parts.append(str(item.get("output_filename", "")))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def generated_dir_matches_confirmation(plan, confirmation):
    plan_dir = str(plan.get("generated_images_dir", "")).replace("/", "\\")
    confirmed_dir = str(confirmation.get("generated_images_dir", "")).replace("/", "\\")
    return plan_dir == confirmed_dir or plan_dir.endswith(confirmed_dir)


def image_count_confirmation_status(workspace: Path, task, run_info, plan):
    policy = task["image_count_policy"]
    count = int(plan.get("expected_image_count", 0))
    threshold = int(policy["confirm_threshold"])
    status = {
        "required": count > threshold,
        "valid": count <= threshold,
        "reason": "not_required" if count <= threshold else "missing_confirmation_file",
        "path": str(workspace / "work" / "image_count_confirmation.json"),
        "expected_image_count": count,
        "confirm_threshold": threshold,
    }
    if count <= threshold:
        return status

    path = workspace / "work" / "image_count_confirmation.json"
    if not path.exists():
        write_image_count_confirmation_template(workspace, task, run_info, plan)
        return status

    confirmation = read_json(path)
    fingerprint = image_plan_fingerprint(plan)
    checks = [
        (confirmation.get("confirmed") is True, "confirmed_not_true"),
        (confirmation.get("run_id") == run_info.get("run_id") == plan.get("run_id"), "run_id_mismatch"),
        (int(confirmation.get("expected_image_count", -1)) == count, "expected_image_count_mismatch"),
        (int(confirmation.get("confirm_threshold", -1)) == threshold, "confirm_threshold_mismatch"),
        (generated_dir_matches_confirmation(plan, confirmation), "generated_images_dir_mismatch"),
        ((not confirmation.get("input_report")) or confirmation.get("input_report") == task.get("input_report"), "input_report_mismatch"),
        ((not confirmation.get("plan_fingerprint")) or confirmation.get("plan_fingerprint") == fingerprint, "plan_fingerprint_mismatch"),
    ]
    failed = [reason for ok, reason in checks if not ok]
    status["valid"] = not failed
    status["reason"] = "confirmed" if not failed else failed[0]
    if failed:
        write_image_count_confirmation_template(workspace, task, run_info, plan)
    return status


def write_image_count_confirmation_template(workspace: Path, task, run_info, plan):
    policy = task["image_count_policy"]
    template = {
        "run_id": run_info.get("run_id"),
        "expected_image_count": plan.get("expected_image_count", 0),
        "confirm_threshold": policy["confirm_threshold"],
        "confirmed": False,
        "confirmed_by": "user",
        "confirmed_at": datetime.now().isoformat(timespec="seconds"),
        "reason": "用户确认本轮允许生成并插入这些图片后，将 confirmed 改为 true。",
        "image_generation_plan_path": "work/image_generation_plan.json",
        "generated_images_dir": plan.get("generated_images_dir"),
        "task_name": task.get("task_name"),
        "input_report": task.get("input_report"),
        "plan_fingerprint": image_plan_fingerprint(plan),
    }
    write_json(workspace / "work" / "image_count_confirmation.template.json", template)
    return template


def task_directives_confirmed(workspace: Path):
    path = workspace / "work" / "task_directives.json"
    if not path.exists():
        return False
    try:
        return valid_confirmation_source(read_json(path))
    except Exception:
        return False


def image_plan_confirmed(workspace: Path):
    path = workspace / "work" / "refined_image_plan.json"
    if not path.exists():
        return False
    try:
        return valid_confirmation_source(read_json(path))
    except Exception:
        return False


def image_insertion_confirmation_ready(workspace: Path) -> bool:
    path = workspace / "work" / "image_insertion_confirmation.md"
    if not path.exists():
        return False
    text = read_text(path)
    return all(marker in text for marker in ("| 图片", "区域类型", "放在哪里", "附近文字/锚点"))


def gpt_image_2_only_required(workspace: Path):
    directives_path = workspace / "work" / "task_directives.json"
    if directives_path.exists():
        directives = read_json(directives_path)
        if (directives.get("image_mode") or {}).get("value") == "gpt_image_2_only":
            return True
    plan_path = workspace / "work" / "refined_image_plan.json"
    if plan_path.exists():
        plan = read_json(plan_path)
        for item in plan.get("items", []):
            if item.get("image_source_policy") == "gpt_image_2_only":
                return True
    return False


def confirmed_experiment_type(workspace: Path) -> str | None:
    path = workspace / "work" / "task_directives.json"
    if not path.exists():
        return None
    try:
        directives = read_json(path)
    except Exception:
        return None
    value = directives.get("experiment_type")
    if isinstance(value, dict):
        value = value.get("value")
    return value if value and value != "pending_gpt_semantic_judgment" else None


def sync_context_resolved_type_from_directives(workspace: Path):
    exp_type = confirmed_experiment_type(workspace)
    if not exp_type:
        return None
    context_path = workspace / "work" / "current_task_context.json"
    if context_path.exists():
        context = read_json(context_path)
        context["resolved_experiment_type"] = exp_type
        context["resolved_experiment_type_source"] = "task_directives"
        write_json(context_path, context)
    startup_path = workspace / "work" / "task_startup_audit.json"
    if startup_path.exists():
        audit = read_json(startup_path)
        audit["resolved_experiment_type"] = exp_type
        audit["resolved_experiment_type_source"] = "task_directives"
        write_json(startup_path, audit)
    return exp_type



def start_or_resume_run(workspace: Path, phase: str, task=None, resolved_input: Path | None = None):
    current_path = workspace / "work" / "current_run.json"
    if phase == "post_images":
        if not current_path.exists():
            raise RuntimeError("post_images requires work/current_run.json")
        return read_json(current_path)
    if phase == "pre_images" and current_path.exists() and task and resolved_input:
        context_path = workspace / "work" / "current_task_context.json"
        current = read_json(current_path)
        context = read_json(context_path) if context_path.exists() else {}
        same_input = context.get("input_report") == str(resolved_input)
        same_stage = context.get("workflow_stage") == task.get("workflow_stage")
        generated_dir = Path(current.get("generated_images_dir", ""))
        if same_input and same_stage and generated_dir.name == "generated_images":
            generated_dir.mkdir(parents=True, exist_ok=True)
            return current
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = workspace / "work" / "runs" / run_id
    generated_dir = run_dir / "generated_images"
    generated_dir.mkdir(parents=True, exist_ok=True)
    current = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "generated_images_dir": str(generated_dir),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_json(current_path, current)
    return current


def safe_report_filename(source_filename: str, fallback_name: str = "实验报告", max_stem_length: int = 90) -> str:
    source_path = Path(source_filename).name if source_filename else ""
    raw = Path(source_path).stem if source_path else (fallback_name or "实验报告")
    raw = raw.strip().strip(".")
    name = re.sub(r'[<>:"/\\|?*]+', "-", raw).strip().strip(".")
    if not name:
        name = "实验报告"
    if len(name) > max_stem_length:
        name = name[:max_stem_length].rstrip(" .")
    return f"{name}.docx"


def report_name(task):
    override = (task.get("output_report_name") or "").strip().strip(".")
    if override:
        override = re.sub(r'[<>:"/\\|?*]+', "-", override)
        if not override.lower().endswith(".docx"):
            override += ".docx"
        return override
    if task.get("workflow_stage") == "first_run_test":
        return "流程测试_实验报告.docx"
    return safe_report_filename(task.get("input_report", ""), task.get("task_name", ""))


def text_counts_from_docx(path: Path):
    if not path or not path.exists():
        return {"triple_question_mark_count": 0, "replacement_char_count": 0}
    from docx import Document

    doc = Document(path)
    text = "\n".join(
        [p.text for p in doc.paragraphs]
        + [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
    )
    return {"triple_question_mark_count": text.count("???"), "replacement_char_count": text.count("\ufffd")}


def write_encoding_report(workspace: Path, input_report: Path, output_report: Path | None = None):
    input_counts = text_counts_from_docx(input_report)
    output_counts = text_counts_from_docx(output_report) if output_report else {"triple_question_mark_count": 0, "replacement_char_count": 0}
    pollution = bool(
        output_report
        and (
            output_counts["triple_question_mark_count"] > input_counts["triple_question_mark_count"]
            or output_counts["replacement_char_count"] > input_counts["replacement_char_count"]
        )
    )
    lines = [
        "# Encoding Report",
        "",
        f"- sys.getdefaultencoding: `{sys.getdefaultencoding()}`",
        f"- sys.getfilesystemencoding: `{sys.getfilesystemencoding()}`",
        f"- locale.getpreferredencoding: `{locale.getpreferredencoding(False)}`",
        f"- stdin encoding: `{getattr(sys.stdin, 'encoding', '')}`",
        f"- stdout encoding: `{getattr(sys.stdout, 'encoding', '')}`",
        f"- stderr encoding: `{getattr(sys.stderr, 'encoding', '')}`",
        f"- PYTHONIOENCODING: `{os.environ.get('PYTHONIOENCODING', '')}`",
        "",
        f"- input_report: `{input_report}`",
        f"- output_report: `{output_report or ''}`",
        f"- input ??? count: {input_counts['triple_question_mark_count']}",
        f"- output ??? count: {output_counts['triple_question_mark_count']}",
        f"- input replacement char count: {input_counts['replacement_char_count']}",
        f"- output replacement char count: {output_counts['replacement_char_count']}",
        f"- encoding_pollution_detected: {pollution}",
    ]
    write_text(workspace / "work" / "encoding_report.md", "\n".join(lines) + "\n")
    return pollution


def write_task_context(workspace: Path, task, run_info, resolved_input, resolved_type):
    if not resolved_type or resolved_type == "auto":
        raise RuntimeError("resolved_experiment_type must not be auto; check analyze_template.py detection.")
    profile_path = workspace / "configs" / "profiles" / f"{resolved_type}.yaml"
    context = {
        "run_id": run_info["run_id"],
        "task_name": task["task_name"],
        "workflow_stage": task["workflow_stage"],
        "experiment_type": task["experiment_type"],
        "resolved_experiment_type": resolved_type,
        "profile_path": str(profile_path),
        "input_report": str(resolved_input),
        "output_dir": task["output_dir"],
        "output_report_name": task.get("output_report_name"),
        "generate_images": task["generate_images"],
        "insert_images": task["insert_images"],
        "fill_text": task["fill_text"],
        "fill_identity_fields": task["fill_identity_fields"],
        "clear_identity_fields": task["clear_identity_fields"],
        "identity_policy": task.get("identity_policy"),
        "use_gpt_text_planner": task["use_gpt_text_planner"],
        "use_gpt_image_planner": task["use_gpt_image_planner"],
        "image_count_policy": task["image_count_policy"],
    }
    write_json(workspace / "work" / "current_task_context.json", context)
    update_startup_audit_run(workspace, run_info, context)
    return context


def update_startup_audit_run(workspace: Path, run_info, context):
    path = workspace / "work" / "task_startup_audit.json"
    if not path.exists():
        return
    audit = read_json(path)
    audit["current_run_id"] = run_info.get("run_id")
    audit["image_output_dir"] = run_info.get("generated_images_dir")
    audit["resolved_experiment_type"] = context.get("resolved_experiment_type")
    write_json(path, audit)
    md = workspace / "work" / "task_startup_audit.md"
    lines = [
        "# Task Startup Audit",
        "",
        f"- task_name: {audit.get('task_name', '')}",
        f"- input_report: `{audit.get('input_report', '')}`",
        f"- output_report_name: `{audit.get('output_report_name') or ''}`",
        f"- workspace: `{audit.get('workspace', '')}`",
        f"- resolved_experiment_type: {audit.get('resolved_experiment_type') or ''}",
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
        f"- current_run_id: {audit.get('current_run_id') or ''}",
        f"- image_output_dir: `{audit.get('image_output_dir') or ''}`",
        "",
        "## Notes",
        "",
    ]
    for note in audit.get("notes", []):
        lines.append(f"- {note}")
    write_text(md, "\n".join(lines) + "\n")


def verify_startup_audit_matches_task(workspace: Path, task):
    path = workspace / "work" / "task_startup_audit.json"
    if not path.exists():
        return
    audit = read_json(path)
    mismatches = []
    if audit.get("task_name") != task.get("task_name"):
        mismatches.append("task_name")
    if audit.get("input_report") != task.get("input_report"):
        mismatches.append("input_report")
    if audit.get("output_report_name") and audit.get("output_report_name") != task.get("output_report_name"):
        mismatches.append("output_report_name")
    if bool(audit.get("fill_identity_fields")) != bool(task.get("fill_identity_fields")):
        mismatches.append("fill_identity_fields")
    if mismatches:
        raise RuntimeError(
            "当前 task.yaml 与 task_startup_audit.json 不一致；"
            "请通过 prepare_new_task.py 重新初始化任务。"
            f" mismatch={', '.join(mismatches)}"
        )


def enforce_audit_gate(workspace: Path):
    path = workspace / "work" / "batch_check_report.json"
    if not path.exists():
        raise RuntimeError("缺少 work/batch_check_report.json，不能声明任务完成。")
    results = read_json(path)
    if not results:
        raise RuntimeError("审计报告为空，不能声明任务完成。")
    failures = []
    for item in results:
        report = item.get("report", "<unknown>")
        expected = int(item.get("expected_image_count", 0) or 0)
        generated = int(item.get("generated_image_count", 0) or 0)
        inserted = int(item.get("inserted_image_count", 0) or 0)
        checks = [
            (item.get("hard_fail") is True, "hard_fail"),
            (item.get("legacy_image_used") is True, "legacy_image_used"),
            (bool(item.get("missing_images")), "missing_images"),
            (bool(item.get("unexpected_images")), "unexpected_images"),
            (expected and generated != expected, "generated_image_count_mismatch"),
            (expected and inserted != expected, "inserted_image_count_mismatch"),
            (item.get("encoding_pollution_detected") is True, "encoding_pollution_detected"),
            (int(item.get("unresolved_image_count") or 0) > 0, "unresolved_image_count"),
            (int(item.get("unresolved_image_insert_count") or 0) > 0, "unresolved_image_insert_count"),
        ]
        reasons = [reason for failed, reason in checks if failed]
        if reasons:
            failures.append(f"{report}: {', '.join(reasons)}")
    if failures:
        raise RuntimeError("审计门禁失败，不能声明任务完成：\n" + "\n".join(failures))


def display_file_for_action(message: str) -> str | None:
    if "task_understanding_confirmation.md" in message:
        return "work/task_understanding_confirmation.md"
    if "image_insertion_confirmation.md" in message:
        return "work/image_insertion_confirmation.md"
    if "latest_user_feedback.md" in message:
        return "work/latest_user_feedback.md"
    if "image_2_generation_todo.md" in message:
        return "work/image_2_generation_todo.md"
    if "image_count_confirmation" in message:
        return "work/image_count_confirmation.template.json"
    return None


def action_required(workspace, entries, message):
    write_audit(workspace, entries)
    display_file = display_file_for_action(message)
    payload = {
        "status": "ACTION_REQUIRED",
        "message": message,
        "display_file": display_file,
        "must_display_inline_to_user": bool(display_file),
        "instruction_to_codex": (
            "If display_file is set, read that file and present its relevant content directly in chat. "
            "Do not only provide a path or attachment."
        ),
    }
    write_json(workspace / "work" / "action_required.json", payload)
    print("ACTION_REQUIRED: " + message)
    if display_file:
        print(f"MUST_DISPLAY_INLINE_TO_USER: {display_file}")
    print(write_audit(workspace, entries))


def stop_for_pending_feedback(workspace, entries):
    feedback = pending_user_feedback(workspace)
    if not feedback:
        return False
    warn_detail = f"{feedback.get('stage')} feedback pending: work/latest_user_feedback.md"
    entries.append({"stage": "user_feedback_revision", "status": "needs_action", "detail": warn_detail})
    action_required(
        workspace,
        entries,
        f"revise {feedback.get('stage')} according to work/latest_user_feedback.md, regenerate confirmation, then resolve feedback",
    )
    return True


def main():
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    phase = sys.argv[2] if len(sys.argv) > 2 else "pre_images"
    skill_root = Path(__file__).resolve().parents[1]
    scripts = skill_root / "scripts"
    entries = []

    def ok(stage, detail):
        entries.append({"stage": stage, "status": "ok", "detail": str(detail).replace("|", "/")})

    def warn(stage, detail):
        entries.append({"stage": stage, "status": "needs_action", "detail": str(detail).replace("|", "/")})

    run(scripts / "init_workspace.py", workspace)
    ok("init_workspace", workspace)
    task = read_task(workspace)
    verify_startup_audit_matches_task(workspace, task)
    input_report = workspace / task["input_report"]
    proc = run(scripts / "convert_legacy_doc.py", workspace, input_report, check=False)
    if proc.returncode != 0:
        write_audit(workspace, entries)
        raise RuntimeError("input resolution failed; see work/input_resolution.json")
    resolved = Path(proc.stdout.splitlines()[0].strip())
    ok("resolve_input", resolved)
    run_info = start_or_resume_run(workspace, phase, task, resolved)
    ok("run", f"{run_info['run_id']} ({run_info['generated_images_dir']})")

    run(scripts / "analyze_template.py", workspace, resolved)
    analysis = read_json(workspace / "work" / "report_analysis.json")
    resolved_type = analysis.get("experiment_type") or task["experiment_type"] or "network_hcl"
    write_task_context(workspace, task, run_info, resolved, resolved_type)
    ok("current_task_context", "work/current_task_context.json")

    run(scripts / "extract_doc_structure.py", workspace, resolved)
    ok("extract_doc_structure", "work/doc_structure.json")

    if stop_for_pending_feedback(workspace, entries):
        return

    if not task_directives_confirmed(workspace):
        run(scripts / "infer_task_directives.py", workspace, check=False)
        warn("task_understanding_confirmation", "work/task_understanding_confirmation.md")
        action_required(workspace, entries, "confirm task understanding before semantic planning; see work/task_understanding_confirmation.md")
        return
    ok("task_directives", "work/task_directives.json confirmed")
    directive_type = sync_context_resolved_type_from_directives(workspace)
    if directive_type:
        resolved_type = directive_type

    run(scripts / "extract_requirement_items.py", workspace)
    ok("extract_requirement_items", "work/requirement_items.json")

    run(scripts / "extract_text_fill_candidates.py", workspace)
    ok("extract_text_fill_candidates", "work/draft_text_fill_candidates.json")
    run(scripts / "extract_image_slot_candidates.py", workspace)
    ok("extract_image_slot_candidates", "work/draft_image_slot_candidates.json")
    write_encoding_report(workspace, resolved, None)
    ok("encoding_report", "work/encoding_report.md")

    text_plan = workspace / "work" / "refined_text_fill_plan.json"
    image_plan = workspace / "work" / "refined_image_plan.json"
    if (task["fill_text"] and not text_plan.exists()) or ((task["generate_images"] or task["insert_images"]) and not image_plan.exists()):
        warn("semantic_planning", "refined_text_fill_plan.json and/or refined_image_plan.json missing")
        action_required(workspace, entries, "refine semantic plans from draft_text_fill_candidates.json and draft_image_slot_candidates.json")
        return

    if task["fill_text"]:
        run(scripts / "validate_plans.py", workspace, "text")
        ok("validate_text_plan", "work/refined_text_fill_plan.json")
    if task["generate_images"] or task["insert_images"]:
        run(scripts / "validate_plans.py", workspace, "image")
        ok("validate_image_plan", "work/refined_image_plan.json")
        if not image_insertion_confirmation_ready(workspace):
            run(scripts / "build_image_insertion_confirmation.py", workspace)
            warn("image_insertion_confirmation", "work/image_insertion_confirmation.md")
            action_required(workspace, entries, "confirm image insertion plan before image generation; see work/image_insertion_confirmation.md")
            return
        if not image_plan_confirmed(workspace):
            run(scripts / "build_image_insertion_confirmation.py", workspace)
            warn("image_insertion_confirmation", "work/image_insertion_confirmation.md")
            action_required(workspace, entries, "confirm image insertion plan before image generation; see work/image_insertion_confirmation.md")
            return
        ok("image_plan_confirmation", "work/refined_image_plan.json confirmed")

    if task["generate_images"] or task["insert_images"]:
        ref_dir = workspace / "assets" / "references" / "hcl"
        if resolved_type == "network_hcl" and (any(ref_dir.glob("*.png")) or any(ref_dir.glob("*.jpg")) or any(ref_dir.glob("*.jpeg"))):
            run(scripts / "analyze_references.py", workspace)
            ok("analyze_references", "work/reference_analysis.md/json")
        run(scripts / "build_image_prompts.py", workspace)
        ok("build_image_prompts", "work/image_prompts.md")
        run(scripts / "prepare_image_generation.py", workspace)
        ok("prepare_image_generation", "work/image_generation_plan.json")
        run(scripts / "validate_plans.py", workspace, "image_generation")
        ok("validate_image_generation_plan", "work/image_generation_plan.json")
        plan = read_json(workspace / "work" / "image_generation_plan.json")
        count = plan.get("expected_image_count", 0)
        policy = task["image_count_policy"]
        if count > policy["hard_limit"]:
            warn("image_count_policy", f"image count {count} exceeds hard limit {policy['hard_limit']}")
            action_required(workspace, entries, "image count exceeds hard limit; explicit user approval required")
            return
        confirmation = image_count_confirmation_status(workspace, task, run_info, plan)
        if confirmation["required"] and not confirmation["valid"]:
            warn(
                "image_count_policy",
                f"image count {count} exceeds confirm threshold {policy['confirm_threshold']}; "
                f"confirmation={confirmation['reason']}; template=work/image_count_confirmation.template.json",
            )
            action_required(workspace, entries, "confirm high image count before generation; create work/image_count_confirmation.json from template and set confirmed=true")
            return
        if confirmation["required"]:
            ok("image_count_confirmation", "work/image_count_confirmation.json")
        if phase != "post_images":
            if gpt_image_2_only_required(workspace):
                warn("image_2_generation", "ACTION_REQUIRED_GENERATE_IMAGE_2_IMAGES; see work/image_2_generation_todo.md")
                action_required(workspace, entries, "ACTION_REQUIRED_GENERATE_IMAGE_2_IMAGES: call image_gen for every item in work/image_generation_plan.json, save outputs to current run generated_images_dir, then write work/generated_images_manifest.json")
            else:
                warn("image_generation", "generate images into current run generated_images_dir")
                action_required(workspace, entries, "generate images from work/image_generation_plan.json")
            return

    output_report = workspace / task["output_dir"] / report_name(task)
    if phase == "post_images":
        if task["generate_images"] or task["insert_images"]:
            if gpt_image_2_only_required(workspace):
                proc = run(scripts / "validate_generated_images_manifest.py", workspace, check=False)
                if proc.returncode != 0:
                    warn("validate_generated_images_manifest", "gpt_image_2_only requires verified generated_images_manifest.json")
                    action_required(workspace, entries, "ACTION_REQUIRED_GENERATE_IMAGE_2_IMAGES: call image_gen, save PNGs with planned output_filename, then write and validate work/generated_images_manifest.json before post_images")
                    return
                ok("validate_generated_images_manifest", "work/generated_images_manifest_audit.md")
        if task["fill_text"]:
            proc = run(scripts / "fill_report.py", workspace, resolved, output_report, check=False)
            if proc.returncode == 2:
                warn("text_fill", "refined_text_fill_plan.json missing")
                action_required(workspace, entries, "refine text fill plan before report filling")
                return
            if proc.returncode != 0:
                raise RuntimeError(f"fill_report.py failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
            ok("fill_report_text", output_report)
            if write_encoding_report(workspace, resolved, output_report):
                raise RuntimeError("Encoding pollution detected after text fill. Regenerate from a clean template.")
        if task["insert_images"]:
            run(scripts / "insert_report_images.py", workspace, output_report)
            ok("insert_report_images", "work/image_list.md")
        run(scripts / "build_requirement_coverage_report.py", workspace)
        ok("requirement_coverage_report", "work/requirement_coverage_report.md")
        run(scripts / "audit_report.py", workspace, output_report)
        ok("audit_report", "work/batch_check_report.md")
        enforce_audit_gate(workspace)
        ok("audit_gate", "passed")

    print(write_audit(workspace, entries))


if __name__ == "__main__":
    main()
