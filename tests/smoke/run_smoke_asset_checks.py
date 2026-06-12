from __future__ import annotations

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parent


REQUIRED_CASES = [
    "01_confirmation_required",
    "02_gpt_image_2_only_no_script_fallback",
    "03_question_area_not_insert",
    "04_zone_type_required",
    "05_long_question_answer_boundary",
    "06_fixed_task_confirmation",
    "07_fixed_image_confirmation",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"cannot read JSON {path}: {exc}")


def main() -> None:
    missing = [case for case in REQUIRED_CASES if not (ROOT / case).is_dir()]
    if missing:
        fail(f"missing smoke case directories: {', '.join(missing)}")

    for case in REQUIRED_CASES:
        case_dir = ROOT / case
        readme = case_dir / "README.md"
        expected = case_dir / "expected.json"
        if not readme.exists():
            fail(f"{case} missing README.md")
        if not expected.exists():
            fail(f"{case} missing expected.json")
        data = load_json(expected)
        if not data:
            fail(f"{case} expected.json is empty")

    q_expected = load_json(ROOT / "03_question_area_not_insert" / "expected.json")
    if "zone_type" != q_expected.get("required_plan_field"):
        fail("03_question_area_not_insert must require zone_type")
    if not q_expected.get("must_fail_without_explicit_allow"):
        fail("03_question_area_not_insert must fail without explicit allow")
    for name in (
        "bad_refined_image_plan.question_area.json",
        "good_refined_image_plan.answer_area.json",
    ):
        if not (ROOT / "03_question_area_not_insert" / name).exists():
            fail(f"03_question_area_not_insert missing fixture {name}")

    z_expected = load_json(ROOT / "04_zone_type_required" / "expected.json")
    if not z_expected.get("must_fail_if_missing"):
        fail("04_zone_type_required must fail if zone_type is missing")
    for name in (
        "bad_refined_image_plan.missing_zone_type.json",
        "bad_refined_text_plan.missing_zone_type.json",
    ):
        if not (ROOT / "04_zone_type_required" / name).exists():
            fail(f"04_zone_type_required missing fixture {name}")

    template = ROOT / "05_long_question_answer_boundary" / "template.docx"
    if not template.exists():
        fail("05_long_question_answer_boundary missing template.docx")
    if template.stat().st_size < 1000:
        fail("05_long_question_answer_boundary template.docx is unexpectedly small")

    first_expected = load_json(ROOT / "06_fixed_task_confirmation" / "expected.json")
    for marker in (
        "# 第一阶段确认",
        "## 本次任务",
        "## 1. 我要做什么",
        "## 2. 实验属于哪一类",
        "## 7. 图片来源策略",
        "## 你可以怎么回复",
    ):
        if marker not in first_expected.get("required_markers", []):
            fail(f"06_fixed_task_confirmation must require marker {marker}")

    second_expected = load_json(ROOT / "07_fixed_image_confirmation" / "expected.json")
    for marker in ("# 第二阶段确认", "| 图片", "放在哪里", "附近文字/锚点", "## 你可以怎么回复"):
        if marker not in second_expected.get("required_markers", []):
            fail(f"07_fixed_image_confirmation must require marker {marker}")

    print("PASS: smoke assets are present and internally consistent")


if __name__ == "__main__":
    main()
