from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
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


def confirmation_mode_value(directives: dict) -> str:
    mode = directives.get("confirmation_mode")
    if isinstance(mode, dict):
        return mode.get("value", "manual_required")
    return mode or "manual_required"


def assert_source_allowed(directives: dict, source: str | None) -> str:
    mode = confirmation_mode_value(directives)
    if not source:
        raise SystemExit(
            "ACTION_REQUIRED_EXPLICIT_USER_CONFIRMATION: "
            "confirmation source is required. Use --source explicit_user_reply only after the user confirms, "
            "or --source agent_auto_allowed_by_user only when confirmation_mode=agent_auto_allowed."
        )
    if mode == "agent_auto_allowed":
        allowed = VALID_MANUAL_CONFIRMATION_SOURCES | VALID_AUTO_CONFIRMATION_SOURCES
    else:
        allowed = VALID_MANUAL_CONFIRMATION_SOURCES
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
    return mode


def assert_semantic_judgment_completed(directives: dict) -> None:
    pending_values = {"pending_gpt_semantic_judgment", "needs_gpt_semantic_judgment"}
    if directives.get("semantic_judgment_required"):
        raise SystemExit(
            "ACTION_REQUIRED_GPT_SEMANTIC_TASK_JUDGMENT: "
            "work/auto_task_directives.json is still a script-produced evidence packet. "
            "Codex/GPT must first write semantic task directives with experiment_type, "
            "document_pattern, writing_mode, coverage_mode, and detail_level, then show the "
            "full first-stage confirmation to the user."
        )
    for key in ("experiment_type", "document_pattern", "writing_mode", "coverage_mode", "detail_level"):
        value = directives.get(key, {})
        if isinstance(value, dict):
            value = value.get("value")
        if value in pending_values:
            raise SystemExit(
                f"ACTION_REQUIRED_GPT_SEMANTIC_TASK_JUDGMENT: {key} is still pending. "
                "Do not confirm until Codex/GPT has made the semantic judgment."
            )


def assert_confirmation_document_exists(workspace: Path) -> None:
    md = workspace / "work" / "task_understanding_confirmation.md"
    if not md.exists():
        raise SystemExit(
            "ACTION_REQUIRED_CONFIRMATION_DOCUMENT_MISSING: "
            "work/task_understanding_confirmation.md must be generated and shown before confirming task understanding."
        )
    text = md.read_text(encoding="utf-8-sig", errors="replace")
    required_markers = (
        "# 第一阶段确认",
        "## 本次任务",
        "## 1. 我要做什么",
        "## 2. 实验属于哪一类",
        "## 4. 报告应该怎么写",
        "## 7. 图片来源策略",
        "## 你可以怎么回复",
    )
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        raise SystemExit(
            "ACTION_REQUIRED_CONFIRMATION_DOCUMENT_INCOMPLETE: "
            f"work/task_understanding_confirmation.md is missing required fixed-format markers: {', '.join(missing)}"
        )


def main():
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    persist = "--persist-profile" in sys.argv
    source = arg_value(sys.argv, "--source")
    auto_path = workspace / "work" / "auto_task_directives.json"
    if not auto_path.exists():
        raise SystemExit("Missing work/auto_task_directives.json; run infer_task_directives.py first.")
    directives = read_json(auto_path)
    assert_semantic_judgment_completed(directives)
    assert_confirmation_document_exists(workspace)
    mode = assert_source_allowed(directives, source)
    directives["confirmed_by_user"] = True
    directives["confirmed_at"] = datetime.now().isoformat(timespec="seconds")
    directives["confirmation_source"] = source
    directives["confirmation_mode"] = mode
    if source in VALID_AUTO_CONFIRMATION_SOURCES:
        directives["auto_confirmation_grant_text"] = arg_value(sys.argv, "--auto-grant-text")

    exp = directives.get("experiment_type", {})
    profile_source = exp.get("profile_source")
    if profile_source and persist:
        src = Path(profile_source)
        if not src.is_absolute():
            src = workspace / src
        target_dir = workspace / "configs" / "profiles" / "discovered"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{exp.get('value', 'auto_discovered_profile')}.yaml"
        shutil.copy2(src, target)
        exp["profile_source"] = str(target)
        exp["persist_profile"] = True
    elif profile_source:
        exp["persist_profile"] = False
    directives["experiment_type"] = exp
    write_json(workspace / "work" / "task_directives.json", directives)
    print(workspace / "work" / "task_directives.json")


if __name__ == "__main__":
    main()
