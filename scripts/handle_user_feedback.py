from __future__ import annotations

from datetime import datetime
from pathlib import Path
import argparse
import re

from utils.file_io import read_json, read_text, write_json, write_text
from utils.fs_safety import configure_utf8_stdio
from utils.fs_safety import safe_delete_file


VALID_STAGES = {
    "task_understanding",
    "text_plan",
    "image_plan",
    "image_generation",
    "final_report",
    "auto",
}

DOWNSTREAM_BY_STAGE = {
    "task_understanding": [
        "work/task_directives.json",
        "work/refined_text_fill_plan.json",
        "work/refined_image_plan.json",
        "work/image_insertion_confirmation.md",
        "work/image_prompts.md",
        "work/image_generation_plan.json",
        "work/image_2_generation_todo.md",
    ],
    "text_plan": [
        "work/image_prompts.md",
        "work/image_generation_plan.json",
        "work/image_2_generation_todo.md",
    ],
    "image_plan": [
        "work/image_insertion_confirmation.md",
        "work/image_prompts.md",
        "work/image_generation_plan.json",
        "work/image_2_generation_todo.md",
    ],
    "image_generation": [
        "work/generated_images_manifest.json",
        "work/generated_images_manifest_audit.json",
        "work/generated_images_manifest_audit.md",
    ],
    "final_report": [],
}


def arg_text(args) -> str:
    if args.feedback_file:
        return read_text(args.feedback_file).strip()
    return (args.feedback_text or "").strip()


def infer_stage(workspace: Path, feedback: str) -> str:
    text = feedback.lower()
    if any(token in text for token in ("实验类型", "任务理解", "填写方式", "不是", "识别错")):
        return "task_understanding"
    if any(token in text for token in ("图片", "插图", "图 ", "图1", "图 1", "位置", "生图", "截图")):
        return "image_plan"
    if any(token in text for token in ("正文", "文字", "太长", "太短", "ai", "总结", "代码")):
        return "text_plan"
    if any(token in text for token in ("重新生成", "重生成", "模糊", "看不清")):
        return "image_generation"
    if (workspace / "work" / "image_insertion_confirmation.md").exists():
        return "image_plan"
    if (workspace / "work" / "task_understanding_confirmation.md").exists() and not (workspace / "work" / "task_directives.json").exists():
        return "task_understanding"
    return "final_report"


def safe_feedback_slug(stage: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{re.sub(r'[^a-z0-9_]+', '_', stage.lower())}"


def read_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = read_json(path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def mark_plan_needs_revision(path: Path, feedback_id: str, feedback: str) -> None:
    data = read_json_if_exists(path)
    if not data:
        return
    data["confirmed_by_user"] = False
    data["feedback_requires_revision"] = True
    data["feedback_id"] = feedback_id
    data["latest_user_feedback"] = feedback
    write_json(path, data)


def remove_downstream(workspace: Path, stage: str) -> list[str]:
    removed = []
    failed = []
    for rel in DOWNSTREAM_BY_STAGE.get(stage, []):
        path = workspace / rel
        if path.exists() and path.is_file():
            try:
                safe_delete_file(path)
                removed.append(rel)
            except OSError as exc:
                failed.append({"path": rel, "error": str(exc)})
    if failed:
        failed_path = workspace / "work" / "feedback_cleanup_warnings.json"
        write_json(failed_path, failed)
    return removed


def record_feedback(workspace: Path, stage: str, feedback: str, source: str) -> dict:
    if not feedback:
        raise SystemExit("Feedback text is empty. Use --feedback-file or --feedback-text.")
    if stage == "auto":
        stage = infer_stage(workspace, feedback)
    if stage not in VALID_STAGES - {"auto"}:
        raise SystemExit(f"Unsupported feedback stage: {stage}")

    feedback_id = safe_feedback_slug(stage)
    record = {
        "feedback_id": feedback_id,
        "stage": stage,
        "status": "pending_revision",
        "source": source,
        "feedback": feedback,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "resolved_at": None,
        "resolution_notes": "",
    }
    out_dir = workspace / "work" / "user_feedback"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / f"{feedback_id}.json", record)
    write_json(workspace / "work" / "latest_user_feedback.json", record)

    if stage == "task_understanding":
        mark_plan_needs_revision(workspace / "work" / "auto_task_directives.json", feedback_id, feedback)
        mark_plan_needs_revision(workspace / "work" / "task_directives.json", feedback_id, feedback)
    elif stage == "text_plan":
        mark_plan_needs_revision(workspace / "work" / "refined_text_fill_plan.json", feedback_id, feedback)
    elif stage == "image_plan":
        mark_plan_needs_revision(workspace / "work" / "refined_image_plan.json", feedback_id, feedback)
    elif stage == "image_generation":
        mark_plan_needs_revision(workspace / "work" / "refined_image_plan.json", feedback_id, feedback)

    removed = remove_downstream(workspace, stage)
    record["removed_stale_outputs"] = removed
    write_json(out_dir / f"{feedback_id}.json", record)
    write_json(workspace / "work" / "latest_user_feedback.json", record)
    write_feedback_md(workspace, record)
    return record


def write_feedback_md(workspace: Path, record: dict) -> None:
    lines = [
        "# User Feedback Revision Request",
        "",
        f"- feedback_id: `{record['feedback_id']}`",
        f"- stage: `{record['stage']}`",
        f"- status: `{record['status']}`",
        f"- source: `{record['source']}`",
        f"- created_at: `{record['created_at']}`",
        "",
        "## User Feedback",
        "",
        record["feedback"],
        "",
        "## Required Codex Action",
        "",
        "- Update the corresponding semantic plan or directives.",
        "- Regenerate the relevant confirmation Markdown.",
        "- Show the revised confirmation to the user.",
        "- After the user approves the revision, run this script with `resolve` and a short resolution note.",
        "",
    ]
    if record.get("removed_stale_outputs"):
        lines.extend(["## Removed Stale Outputs", ""])
        lines.extend(f"- `{item}`" for item in record["removed_stale_outputs"])
        lines.append("")
    write_text(workspace / "work" / "latest_user_feedback.md", "\n".join(lines))


def resolve_feedback(workspace: Path, notes: str) -> dict:
    path = workspace / "work" / "latest_user_feedback.json"
    if not path.exists():
        raise SystemExit("No pending feedback found.")
    record = read_json(path)
    if record.get("status") != "pending_revision":
        return record
    record["status"] = "resolved"
    record["resolved_at"] = datetime.now().isoformat(timespec="seconds")
    record["resolution_notes"] = notes.strip() or "Revision applied and confirmation regenerated."
    write_json(path, record)
    feedback_path = workspace / "work" / "user_feedback" / f"{record['feedback_id']}.json"
    write_json(feedback_path, record)
    write_feedback_md(workspace, record)
    return record


def status(workspace: Path) -> dict:
    path = workspace / "work" / "latest_user_feedback.json"
    if not path.exists():
        return {"status": "none"}
    return read_json(path)


def main() -> None:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Record or resolve natural-language user feedback for lab-report revisions.")
    parser.add_argument("workspace")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record")
    record.add_argument("--stage", choices=sorted(VALID_STAGES), default="auto")
    record.add_argument("--feedback-file")
    record.add_argument("--feedback-text")
    record.add_argument("--source", default="explicit_user_reply")

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--notes", default="")

    sub.add_parser("status")

    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    if args.command == "record":
        result = record_feedback(workspace, args.stage, arg_text(args), args.source)
        print(f"ACTION_REQUIRED_REVISE_{result['stage'].upper()}: {workspace / 'work' / 'latest_user_feedback.md'}")
    elif args.command == "resolve":
        result = resolve_feedback(workspace, args.notes)
        print(f"RESOLVED_USER_FEEDBACK: {result.get('feedback_id')}")
    else:
        result = status(workspace)
        print(result.get("status", "none"))


if __name__ == "__main__":
    main()
