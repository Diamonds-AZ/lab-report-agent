from pathlib import Path
import sys

from utils.file_io import read_json


def fail(message):
    print(f"ACTION_REQUIRED: {message}")
    raise SystemExit(2)


def require_fields(obj, fields, where):
    missing = [field for field in fields if field not in obj]
    if missing:
        fail(f"{where} missing required fields: {', '.join(missing)}")


def reject_utf8_bom(path: Path) -> None:
    if path.exists() and path.read_bytes().startswith(b"\xef\xbb\xbf"):
        fail(f"{path} starts with a UTF-8 BOM; rewrite it through scripts/utils/file_io.py without BOM")


def validate_text_plan(workspace):
    path = workspace / "work" / "refined_text_fill_plan.json"
    if not path.exists():
        fail("work/refined_text_fill_plan.json is missing")
    reject_utf8_bom(path)
    plan = read_json(path)
    require_fields(plan, ["plan_stage", "source_stage", "items", "unresolved"], str(path))
    if plan["plan_stage"] != "refined" or plan["source_stage"] != "gpt_semantic_planning":
        fail("refined_text_fill_plan.json must be refined and source_stage=gpt_semantic_planning")
    for item in plan.get("items", []):
        require_fields(
            item,
            ["item_id", "block_id", "is_text_fill", "fill_type", "slot_index", "left_context", "right_context", "answer", "replacement_strategy", "confidence", "need_user_review", "reason", "zone_type"],
            f"text item {item.get('item_id', '<unknown>')}",
        )
        if item.get("is_text_fill") and item.get("zone_type") in ("question_area", "reference_material"):
            if not item.get("explicitly_allowed_question_area_edit"):
                fail(
                    f"text item {item.get('item_id', '<unknown>')} targets {item.get('zone_type')}; "
                    "question/reference text must not be edited unless explicitly allowed"
                )


def validate_image_plan(workspace):
    path = workspace / "work" / "refined_image_plan.json"
    if not path.exists():
        fail("work/refined_image_plan.json is missing")
    reject_utf8_bom(path)
    plan = read_json(path)
    require_fields(plan, ["plan_stage", "source_stage", "items", "skipped_candidates", "unresolved"], str(path))
    if plan["plan_stage"] != "refined" or plan["source_stage"] != "gpt_semantic_planning":
        fail("refined_image_plan.json must be refined and source_stage=gpt_semantic_planning")
    for item in plan.get("items", []):
        if not item.get("is_image_required"):
            continue
        require_fields(
            item,
            ["image_item_id", "source_candidate_id", "block_id", "is_image_required", "confidence", "slot_type", "target_table_index", "layout_type", "requires_generated_image", "image_kind", "step_context", "prompt_topic", "need_user_review", "reason", "zone_type"],
            f"image item {item.get('image_item_id', '<unknown>')}",
        )
        if item.get("zone_type") in ("question_area", "reference_material"):
            if not item.get("explicitly_allowed_question_area_image"):
                fail(
                    f"image item {item.get('image_item_id', '<unknown>')} targets {item.get('zone_type')}; "
                    "images must not be inserted into question/reference areas unless explicitly allowed"
                )


def validate_image_generation_plan(workspace):
    current_path = workspace / "work" / "current_run.json"
    plan_path = workspace / "work" / "image_generation_plan.json"
    if not current_path.exists() or not plan_path.exists():
        fail("current_run.json or image_generation_plan.json is missing")
    reject_utf8_bom(plan_path)
    current = read_json(current_path)
    plan = read_json(plan_path)
    require_fields(plan, ["run_id", "run_dir", "generated_images_dir", "expected_image_count", "items"], str(plan_path))
    if current.get("run_id") != plan.get("run_id"):
        fail("run_id mismatch between current_run.json and image_generation_plan.json")
    generated_dir = Path(plan["generated_images_dir"])
    if generated_dir.name != "generated_images" or generated_dir.parent.name != plan["run_id"]:
        fail("generated_images_dir must be work/runs/<run_id>/generated_images")
    if plan["expected_image_count"] != len(plan.get("items", [])):
        fail("expected_image_count does not match image_generation_plan item count")
    for item in plan.get("items", []):
        require_fields(item, ["image_id", "image_item_id", "target_table_index", "step_context", "output_filename", "prompt", "status", "zone_type"], f"image generation item {item.get('image_id', '<unknown>')}")
        if item.get("zone_type") in ("question_area", "reference_material") and not item.get("explicitly_allowed_question_area_image"):
            fail(f"image generation item {item.get('image_id', '<unknown>')} targets forbidden zone {item.get('zone_type')}")


def main():
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    mode = sys.argv[2] if len(sys.argv) > 2 else "semantic"
    if mode in ("semantic", "text"):
        validate_text_plan(workspace)
    if mode in ("semantic", "image"):
        validate_image_plan(workspace)
    if mode in ("image_generation", "all"):
        validate_image_generation_plan(workspace)
    if mode == "all":
        validate_text_plan(workspace)
        validate_image_plan(workspace)
    print(f"validated {mode}")


if __name__ == "__main__":
    main()
