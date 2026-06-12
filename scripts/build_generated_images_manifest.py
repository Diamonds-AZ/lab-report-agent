from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import sys

from PIL import Image
from utils.file_io import read_json, write_json
from utils.fs_safety import configure_utf8_stdio


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def image_size(path: Path):
    with Image.open(path) as img:
        return img.size


def gpt_image2_required(workspace: Path, plan: dict) -> bool:
    directives_path = workspace / "work" / "task_directives.json"
    if directives_path.exists():
        directives = read_json(directives_path)
        if (directives.get("image_mode") or {}).get("value") == "gpt_image_2_only":
            return True
    return any(
        item.get("image_source_policy") == "gpt_image_2_only"
        or item.get("image_source") == "gpt_image_2"
        for item in plan.get("items", [])
    )


def fail(message: str) -> None:
    raise SystemExit(message)


def main():
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    source = sys.argv[2] if len(sys.argv) > 2 else "manual_provided"
    created_by = sys.argv[3] if len(sys.argv) > 3 else source
    plan_path = workspace / "work" / "image_generation_plan.json"
    if not plan_path.exists():
        raise SystemExit("Missing work/image_generation_plan.json")
    plan = read_json(plan_path)
    required_image2 = gpt_image2_required(workspace, plan)
    if required_image2:
        if source != "gpt_image_2" or created_by != "image_2":
            fail(
                "gpt_image_2_only requires manifest source arguments: "
                "build_generated_images_manifest.py <workspace> gpt_image_2 image_2"
            )
    forbidden_as_image2 = {"script_reference", "synthetic_hcl", "synthetic_datagrip", "dummy_for_smoke_test", "placeholder", "manual_provided", "real_screenshot"}
    if source == "gpt_image_2" and created_by != "image_2":
        fail("declared_source=gpt_image_2 requires created_by=image_2")
    if source in forbidden_as_image2 and created_by == "image_2":
        fail(f"{source} cannot be registered as created_by=image_2")
    generated_dir = Path(plan["generated_images_dir"])
    items = []
    for item in plan.get("items", []):
        path = generated_dir / item["output_filename"]
        if not path.exists():
            raise SystemExit(f"Missing image: {path}")
        width, height = image_size(path)
        items.append(
            {
                "image_id": item["image_id"],
                "slot_id": item.get("image_item_id"),
                "filename": item["output_filename"],
                "sha256": sha256(path),
                "width": width,
                "height": height,
                "declared_source": source,
                "created_by": created_by,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "prompt_ref": f"image_prompts.md#{item['image_id']}",
                "generation_mode": "gpt_image_2_only" if required_image2 else (item.get("image_source_policy") or source),
                "covered_requirement_ids": item.get("covered_requirement_ids", []),
                "manual_confirmed_source": source != "unknown",
            }
        )
    manifest = {
        "run_id": plan.get("run_id"),
        "generated_images_dir": plan.get("generated_images_dir"),
        "items": items,
    }
    write_json(workspace / "work" / "generated_images_manifest.json", manifest)
    print(workspace / "work" / "generated_images_manifest.json")


if __name__ == "__main__":
    main()
