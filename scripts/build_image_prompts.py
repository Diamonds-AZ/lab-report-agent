from pathlib import Path
import re
import sys

from utils.file_io import read_json, read_text, write_text


PROFILE_TO_PLATFORM = {
    "network_hcl": {
        "platform": "H3C HCL / H3C Cloud Lab",
        "reference_dir": "assets/references/hcl",
        "must": "H3C HCL network simulator, left dark device palette, top gray toolbar, light grid topology canvas, H3C black console window, HCL-style router/switch/PC icons",
        "avoid": "Huawei eNSP, Cisco Packet Tracer, Packet Tracer bottom device bar, GNS3, Cisco logo, Huawei logo",
    },
    "database_datagrip": {
        "platform": "JetBrains DataGrip",
        "reference_dir": "assets/references/datagrip",
        "must": "JetBrains DataGrip English interface, database tree, SQL editor, result grid, console/output panel",
        "avoid": "Navicat, DBeaver, SQLyog, MySQL Workbench",
    },
    "java_idea": {
        "platform": "IntelliJ IDEA",
        "reference_dir": "assets/references/idea",
        "must": "IntelliJ IDEA English interface, Project tree, Java source code editor, Run console",
        "avoid": "Eclipse, NetBeans",
    },
    "web_vscode": {
        "platform": "VS Code + browser preview",
        "reference_dir": "assets/references/vscode",
        "must": "VS Code interface, code editor, terminal or browser preview",
        "avoid": "unrelated IDEs",
    },
    "c_data_structure": {
        "platform": "VC++6.0 / DEV-C++ C console program",
        "reference_dir": "assets/references/c_console",
        "must": "C source code editor or console program window, menu options, input data, readable running result, algorithm-related output",
        "avoid": "DataGrip, HCL, IntelliJ IDEA Java project, web browser UI, unrelated IDEs",
    },
    "c_cpp_console": {
        "platform": "VC++6.0 / DEV-C++ C/C++ console program",
        "reference_dir": "assets/references/c_console",
        "must": "C/C++ source code editor or console program window, menu options, input data, readable running result",
        "avoid": "DataGrip, HCL, IntelliJ IDEA Java project, web browser UI, unrelated IDEs",
    },
    "generic_report": {
        "platform": "the target software or runtime environment described by the lab report",
        "reference_dir": "assets/references/generic",
        "must": "the required code, command, output, or result evidence described by the lab report",
        "avoid": "unrelated software interfaces, personal information, watermarks",
    },
}


def safe_slug(text):
    tokens = [t for t in re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower().split("_") if t]
    deduped = []
    for token in tokens:
        if deduped and deduped[-1] == token:
            continue
        if token in ("hcl", "verify", "verification") and token in deduped:
            continue
        deduped.append(token)
    return "_".join(deduped[:8]) or "screenshot"


def output_filename_for_item(image_id, item):
    if item.get("output_filename"):
        return item["output_filename"]
    step = re.search(r"步骤\s*(\d+)", item.get("step_context", ""))
    step_token = f"step{step.group(1)}" if step else item.get("image_item_id", "screenshot")
    kind_tokens = safe_slug(item.get("image_kind") or "screenshot").split("_")
    topic = safe_slug(item.get("prompt_topic") or item.get("step_context") or "screenshot")
    tokens = []
    for token in [step_token, *kind_tokens, *topic.split("_")]:
        if token and token not in tokens:
            tokens.append(token)
    return f"{image_id}_{'_'.join(tokens[:5])}.png"


def load_context(workspace):
    directives_path = workspace / "work" / "task_directives.json"
    if directives_path.exists():
        directives = read_json(directives_path)
        value = directives.get("experiment_type")
        if isinstance(value, dict):
            value = value.get("value")
        if value:
            return {"resolved_experiment_type": value, "resolved_experiment_type_source": "task_directives"}
    path = workspace / "work" / "current_task_context.json"
    if path.exists():
        return read_json(path)
    analysis = workspace / "work" / "report_analysis.json"
    exp = read_json(analysis).get("experiment_type", "network_hcl") if analysis.exists() else "network_hcl"
    return {"resolved_experiment_type": exp}


def reference_constraints(workspace, image_kind):
    if image_kind != "network_hcl":
        return ""
    json_path = workspace / "work" / "reference_analysis.json"
    if json_path.exists():
        data = read_json(json_path)
        parts = []
        refs = data.get("reference_images") or []
        if refs:
            parts.append("Use these HCL reference image paths as visual style references when supported: " + "; ".join(refs))
        usage = data.get("reference_usage")
        if usage:
            parts.append("reference_usage: " + usage)
        for key in ("window_layout", "toolbar_style", "topology_canvas_style", "device_icon_style", "cli_window_style"):
            values = data.get(key) or []
            if values:
                parts.append(f"{key}: " + "; ".join(values))
        forbidden = data.get("forbidden_copy_content") or []
        if forbidden:
            parts.append("Do not copy: " + "; ".join(forbidden))
        return " ".join(parts)
    md_path = workspace / "work" / "reference_analysis.md"
    return read_text(md_path)[:2000] if md_path.exists() else ""


def validate_refined_image_plan(plan):
    if plan.get("plan_stage") != "refined":
        raise RuntimeError("refined_image_plan.json must set plan_stage='refined'.")
    if plan.get("source_stage") != "gpt_semantic_planning":
        raise RuntimeError("refined_image_plan.json must set source_stage='gpt_semantic_planning'.")
    for item in plan.get("items", []):
        if not item.get("is_image_required"):
            continue
        for key in ("image_item_id", "block_id", "step_context", "prompt_topic", "image_kind", "confidence", "reason", "zone_type"):
            if key not in item:
                raise RuntimeError(f"Image plan item missing required field {key}: {item}")
        if item.get("zone_type") in ("question_area", "reference_material") and not item.get("explicitly_allowed_question_area_image"):
            raise RuntimeError(
                f"Image plan item {item.get('image_item_id')} targets {item.get('zone_type')}; "
                "do not build prompts for question/reference areas unless explicitly allowed."
            )


def main():
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    refined_path = workspace / "work" / "refined_image_plan.json"
    if not refined_path.exists():
        message = "ACTION_REQUIRED: work/refined_image_plan.json is missing. Codex/GPT must refine draft_image_slot_candidates.json before image prompts can be built."
        write_text(workspace / "work" / "image_prompts.md", "# Image Prompts\n\n" + message + "\n")
        print(message)
        raise SystemExit(2)

    plan = read_json(refined_path)
    validate_refined_image_plan(plan)
    context = load_context(workspace)

    required = [item for item in plan.get("items", []) if item.get("is_image_required")]
    lines = [
        "# Image Prompts",
        "",
        f"- source: `{refined_path}`",
        f"- expected_image_count: {len(required)}",
        "",
    ]

    for n, item in enumerate(required, 1):
        image_id = f"IMG-{n:03d}"
        image_kind = item.get("image_kind") or context.get("resolved_experiment_type") or "network_hcl"
        profile = PROFILE_TO_PLATFORM.get(image_kind, PROFILE_TO_PLATFORM["generic_report"])
        ref_text = reference_constraints(workspace, image_kind)
        output_filename = output_filename_for_item(image_id, item)
        covered = item.get("covered_requirement_ids") or item.get("requirement_ids") or []
        must_code = item.get("must_show_code_or_sql") or item.get("must_show_commands") or item.get("must_show_code") or []
        must_result = item.get("must_show_result") or []
        must_message = item.get("must_show_error_or_success_message") or []
        prompt = (
            f"Create a realistic desktop software screenshot for {profile['platform']}. "
            f"Task: {item.get('prompt_topic')}. Step context: {item.get('step_context')}. "
            f"Must include {profile['must']}. Avoid {profile['avoid']}. "
            f"Covered requirement IDs: {', '.join(covered) if covered else 'not specified'}. "
            f"Must show code/SQL/commands if listed: {'; '.join(must_code) if isinstance(must_code, list) else must_code}. "
            f"Must show results if listed: {'; '.join(must_result) if isinstance(must_result, list) else must_result}. "
            f"Must show success/error messages if listed: {'; '.join(must_message) if isinstance(must_message, list) else must_message}. "
            "Use reference images only for interface style, window structure, toolbar/canvas/console placement, colors, fonts, and visual fidelity when references are provided. "
            "Do not copy reference project names, file paths, unrelated commands, personal information, student name, student ID, class, or watermark. "
            "Do not add non-platform UI elements. "
            f"{ref_text}"
        )
        lines.extend(
            [
                f"## {image_id} {item['image_item_id']}",
                "",
                f"- image_item_id: {item['image_item_id']}",
                f"- target_table_index: {item.get('target_table_index')}",
                f"- step_context: {item.get('step_context')}",
                f"- output_filename: {output_filename}",
                f"- image_kind: {image_kind}",
                f"- image_source_policy: {item.get('image_source_policy') or ''}",
                f"- covered_requirement_ids: {', '.join(covered)}",
                "- prompt:",
                "",
                prompt,
                "",
            ]
        )

    write_text(workspace / "work" / "image_prompts.md", "\n".join(lines))
    print(workspace / "work" / "image_prompts.md")


if __name__ == "__main__":
    main()
