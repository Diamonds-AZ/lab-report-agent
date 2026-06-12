from pathlib import Path
import re
import sys

from utils.file_io import read_json, read_text, write_json, write_text


def clean_output_filename(image_id, filename):
    stem = Path(filename).stem if filename else image_id
    ext = Path(filename).suffix.lower() or ".png"
    raw_tokens = [t for t in re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").split("_") if t]
    tokens = []
    image_num = image_id.split("-", 1)[-1].lstrip("0") or image_id
    idx = 0
    if len(raw_tokens) >= 2 and raw_tokens[0].lower() == "img" and raw_tokens[1].lstrip("0") == image_num:
        idx = 2
    for token in raw_tokens[idx:]:
        lower = token.lower()
        if lower == image_id.lower():
            continue
        if lower == image_num and any(t.lower() in (f"step{image_num}", image_num) for t in tokens):
            continue
        if tokens and tokens[-1].lower() == lower:
            continue
        if lower in ("hcl", "verify", "verification") and any(t.lower() == lower for t in tokens):
            continue
        tokens.append(token)
    if not tokens:
        tokens = ["screenshot"]
    return f"{image_id}_{'_'.join(tokens[:8])}{ext}"


def extract_prompt_sections(image_prompts_md: Path):
    text = read_text(image_prompts_md) if image_prompts_md.exists() else ""
    sections = re.split(r"\n##\s+", "\n" + text)
    prompts = {}
    for section in sections:
        header = section.strip().splitlines()[0] if section.strip() else ""
        m = re.match(r"(IMG-\d+)\s+(\S+)", header)
        if not m:
            continue
        image_id, image_item_id = m.groups()
        output_match = re.search(r"-\s*output_filename:\s*(.+)", section)
        prompt_match = re.search(r"-\s*prompt:\s*\n\n(.*)", section, re.S)
        prompts[image_item_id] = {
            "image_id": image_id,
            "output_filename": output_match.group(1).strip() if output_match else f"{image_id}.png",
            "prompt": prompt_match.group(1).strip() if prompt_match else section.strip(),
        }
    return prompts


def current_run(workspace: Path):
    path = workspace / "work" / "current_run.json"
    if not path.exists():
        raise RuntimeError("Missing work/current_run.json; run pre_images first.")
    data = read_json(path)
    run_id = data["run_id"]
    generated_dir = Path(data["generated_images_dir"])
    if not generated_dir.is_absolute():
        generated_dir = workspace / generated_dir
    if generated_dir.name != "generated_images" or generated_dir.parent.name != run_id:
        raise RuntimeError("generated_images_dir must be work/runs/<run_id>/generated_images")
    generated_dir.mkdir(parents=True, exist_ok=True)
    return data, generated_dir


def image_source_for_item(item, workspace: Path):
    if item.get("image_source"):
        return item["image_source"]
    if item.get("image_source_policy") == "gpt_image_2_only":
        return "gpt_image_2"
    directives_path = workspace / "work" / "task_directives.json"
    if directives_path.exists():
        directives = read_json(directives_path)
        mode = (directives.get("image_mode") or {}).get("value")
        if mode == "gpt_image_2_only":
            return "gpt_image_2"
        if mode == "real_screenshot_only":
            return "real_screenshot"
        if mode == "user_provided_only":
            return "manual_provided"
        if mode == "script_reference":
            return "script_reference"
    task_path = workspace / "configs" / "task.yaml"
    task_text = read_text(task_path) if task_path.exists() else ""
    model = ""
    for line in task_text.splitlines():
        if line.strip().startswith("image_generation_model:"):
            model = line.split(":", 1)[1].strip().strip('"').strip("'")
            break
    if model in ("gpt-image-2", "image-2"):
        return "unknown"
    return "unknown"


def gpt_image_2_only_required(workspace: Path, plan_items: list[dict]) -> bool:
    directives_path = workspace / "work" / "task_directives.json"
    if directives_path.exists():
        directives = read_json(directives_path)
        if (directives.get("image_mode") or {}).get("value") == "gpt_image_2_only":
            return True
    return any(
        item.get("image_source_policy") == "gpt_image_2_only"
        or item.get("image_source") == "gpt_image_2"
        for item in plan_items
    )


def write_image_2_todo(workspace: Path, plan: dict) -> None:
    if not gpt_image_2_only_required(workspace, plan.get("items", [])):
        return
    lines = [
        "# ACTION_REQUIRED_GENERATE_IMAGE_2_IMAGES",
        "",
        "本任务要求 `gpt_image_2_only`。",
        "",
        "你必须对 `work/image_generation_plan.json` 中的每一个图片项调用 `image_gen`。",
        "",
        "## 禁止",
        "",
        "- 使用 PIL / HTML / matplotlib 生成图片；",
        "- 使用 dummy / placeholder 图片；",
        "- 使用 synthetic_hcl / synthetic_datagrip / script_reference 图片；",
        "- 使用旧 run 图片；",
        "- 使用 assets/generated_images、output/images 或 .codex/generated_images；",
        "- 为了通过流程而伪造 image-2 来源。",
        "",
        "## 生成后必须做",
        "",
        "1. 将每张图片保存到当前 run 的 generated_images 目录；",
        "2. 文件名必须等于对应图片项的 `output_filename`；",
        "3. 运行 `build_generated_images_manifest.py <workspace> gpt_image_2 image_2` 登记来源；",
        "4. 运行 `validate_generated_images_manifest.py <workspace>` 校验；",
        "5. 校验通过后才能运行 `post_images`。",
        "",
        f"- run_id: `{plan.get('run_id')}`",
        f"- generated_images_dir: `{plan.get('generated_images_dir')}`",
        f"- expected_image_count: {plan.get('expected_image_count')}",
        "",
        "## 图片任务",
        "",
    ]
    for item in plan.get("items", []):
        lines.extend(
            [
                f"### {item.get('image_id')} {item.get('image_item_id')}",
                "",
                f"- output_filename: `{item.get('output_filename')}`",
                f"- image_source_policy: `{item.get('image_source_policy') or 'gpt_image_2_only'}`",
                f"- covered_requirement_ids: {', '.join(item.get('covered_requirement_ids') or [])}",
                "- prompt:",
                "",
                str(item.get("prompt", "")).strip(),
                "",
            ]
        )
    write_text(workspace / "work" / "image_2_generation_todo.md", "\n".join(lines).rstrip() + "\n")
    run_dir = Path(plan.get("run_dir", ""))
    if run_dir:
        write_text(run_dir / "image_2_generation_todo.md", "\n".join(lines).rstrip() + "\n")


def main():
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    refined_path = workspace / "work" / "refined_image_plan.json"
    if not refined_path.exists():
        print("ACTION_REQUIRED: work/refined_image_plan.json is missing")
        raise SystemExit(2)

    refined = read_json(refined_path)
    run, generated_dir = current_run(workspace)
    prompts = extract_prompt_sections(workspace / "work" / "image_prompts.md")
    required = [item for item in refined.get("items", []) if item.get("is_image_required")]
    items = []
    for n, item in enumerate(required, 1):
        image_item_id = item["image_item_id"]
        prompt_info = prompts.get(image_item_id, {})
        image_id = prompt_info.get("image_id") or f"IMG-{n:03d}"
        output_filename = clean_output_filename(
            image_id,
            prompt_info.get("output_filename") or item.get("output_filename") or f"{image_id}.png",
        )
        items.append(
            {
                "image_id": image_id,
                "image_item_id": image_item_id,
                "target_table_index": item.get("target_table_index"),
                "target_row_index": item.get("target_row_index"),
                "target_cell_index": item.get("target_cell_index"),
                "target_anchor": item.get("target_anchor"),
                "target_block_range": item.get("target_block_range"),
                "layout_type": item.get("layout_type"),
                "zone_type": item.get("zone_type"),
                "explicitly_allowed_question_area_image": item.get("explicitly_allowed_question_area_image", False),
                "step_context": item.get("step_context"),
                "output_filename": output_filename,
                "prompt": prompt_info.get("prompt", item.get("prompt_topic", "")),
                "image_source": image_source_for_item(item, workspace),
                "image_source_policy": item.get("image_source_policy"),
                "covered_requirement_ids": item.get("covered_requirement_ids") or item.get("requirement_ids") or [],
                "status": "pending_image_gen",
            }
        )

    plan = {
        "run_id": run["run_id"],
        "run_dir": run["run_dir"],
        "generated_images_dir": str(generated_dir),
        "source_refined_image_plan": str(refined_path),
        "expected_image_count": len(items),
        "items": items,
        "instruction": "Call image_gen/image-2 once per item, then copy each PNG to generated_images_dir using output_filename exactly. post_images reads only this current run directory. Do not use assets/generated_images, output/images, .codex/generated_images, or older run directories as insertion sources.",
    }
    if gpt_image_2_only_required(workspace, items):
        plan["required_generation_action"] = "ACTION_REQUIRED_GENERATE_IMAGE_2_IMAGES"
        plan["instruction"] = (
            "This task is gpt_image_2_only. Codex/Agent must call image_gen once per item, save each generated PNG "
            "to generated_images_dir using output_filename exactly, then create work/generated_images_manifest.json "
            "with declared_source=gpt_image_2 and created_by=image_2. Do not use scripts, dummy images, synthetic images, "
            "legacy images, output/images, .codex/generated_images, assets/generated_images, or older run directories."
        )
    run_plan_path = Path(run["run_dir"]) / "image_generation_plan.json"
    write_json(run_plan_path, plan)
    write_json(workspace / "work" / "image_generation_plan.json", plan)
    write_image_2_todo(workspace, plan)
    run["image_generation_plan"] = str(run_plan_path)
    write_json(workspace / "work" / "current_run.json", run)
    print(run_plan_path)


if __name__ == "__main__":
    main()
