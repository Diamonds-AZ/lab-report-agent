from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from utils.file_io import read_json, write_json
from utils.fs_safety import configure_utf8_stdio
from utils.confirmation import VALID_MANUAL_CONFIRMATION_SOURCES, VALID_AUTO_CONFIRMATION_SOURCES


def arg_value(args: list[str], name: str, default: str | None = None) -> str | None:
    if name not in args:
        return default
    idx = args.index(name)
    if idx + 1 >= len(args):
        raise SystemExit(f"{name} requires a value")
    return args[idx + 1]


def task_confirmation_mode(workspace: Path) -> str:
    path = workspace / "work" / "task_directives.json"
    if not path.exists():
        return "manual_required"
    task = read_json(path)
    mode = task.get("confirmation_mode")
    if isinstance(mode, dict):
        return mode.get("value", "manual_required")
    return mode or "manual_required"


def assert_source_allowed(mode: str, source: str | None) -> None:
    if not source:
        raise SystemExit(
            "ACTION_REQUIRED_EXPLICIT_USER_CONFIRMATION: "
            "confirmation source is required. Use --source explicit_user_reply only after the user confirms, "
            "or --source agent_auto_allowed_by_user only when confirmation_mode=agent_auto_allowed."
        )
    allowed = VALID_MANUAL_CONFIRMATION_SOURCES | VALID_AUTO_CONFIRMATION_SOURCES if mode == "agent_auto_allowed" else VALID_MANUAL_CONFIRMATION_SOURCES
    if source not in allowed:
        raise SystemExit(
            f"ACTION_REQUIRED_EXPLICIT_USER_CONFIRMATION: source={source} is not allowed when confirmation_mode={mode}."
        )
    if source in VALID_AUTO_CONFIRMATION_SOURCES:
        grant_text = arg_value(sys.argv, "--auto-grant-text")
        if not grant_text or not grant_text.strip():
            raise SystemExit(
                "ACTION_REQUIRED_EXPLICIT_AUTO_CONFIRMATION_GRANT: "
                "agent auto-confirmation requires --auto-grant-text with the user's explicit automation request."
            )


def assert_confirmation_document_exists(workspace: Path) -> None:
    md = workspace / "work" / "image_insertion_confirmation.md"
    if not md.exists():
        raise SystemExit(
            "ACTION_REQUIRED_CONFIRMATION_DOCUMENT_MISSING: "
            "work/image_insertion_confirmation.md must be generated and shown before confirming the image plan."
        )
    text = md.read_text(encoding="utf-8-sig", errors="replace")
    required_markers = ("| 图片", "区域类型", "放在哪里", "附近文字/锚点")
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        raise SystemExit(
            "ACTION_REQUIRED_CONFIRMATION_DOCUMENT_INCOMPLETE: "
            f"work/image_insertion_confirmation.md is missing required table markers: {', '.join(missing)}"
        )


def main():
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    source = arg_value(sys.argv, "--source")
    mode = task_confirmation_mode(workspace)
    assert_source_allowed(mode, source)
    assert_confirmation_document_exists(workspace)
    path = workspace / "work" / "refined_image_plan.json"
    if not path.exists():
        raise SystemExit("Missing work/refined_image_plan.json")
    plan = read_json(path)
    plan["confirmed_by_user"] = True
    plan["confirmed_at"] = datetime.now().isoformat(timespec="seconds")
    plan["confirmation_source"] = source
    plan["confirmation_mode"] = mode
    if source in VALID_AUTO_CONFIRMATION_SOURCES:
        plan["auto_confirmation_grant_text"] = arg_value(sys.argv, "--auto-grant-text")
    write_json(path, plan)
    print(path)


if __name__ == "__main__":
    main()
