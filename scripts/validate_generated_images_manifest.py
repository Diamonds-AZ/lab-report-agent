from __future__ import annotations

from pathlib import Path
import hashlib
import sys

from PIL import Image
from utils.file_io import read_json, write_json, write_text
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
    directives = read_json(directives_path) if directives_path.exists() else {}
    mode = (directives.get("image_mode") or {}).get("value")
    if mode == "gpt_image_2_only":
        return True
    for item in plan.get("items", []):
        if item.get("image_source_policy") == "gpt_image_2_only" or item.get("image_source") == "gpt_image_2":
            return True
    return False


def main():
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    plan_path = workspace / "work" / "image_generation_plan.json"
    if not plan_path.exists():
        raise SystemExit("Missing work/image_generation_plan.json")
    plan = read_json(plan_path)
    manifest_path = workspace / "work" / "generated_images_manifest.json"
    required_image2 = gpt_image2_required(workspace, plan)
    if not manifest_path.exists():
        if required_image2:
            raise SystemExit("ACTION_REQUIRED_GENERATE_IMAGE_2_IMAGES: missing generated_images_manifest.json")
        raise SystemExit("Missing work/generated_images_manifest.json")
    manifest = read_json(manifest_path)
    if isinstance(manifest, dict):
        if manifest.get("run_id") and manifest.get("run_id") != plan.get("run_id"):
            raise SystemExit("generated_images_manifest run_id mismatch")
        manifest_dir = str(manifest.get("generated_images_dir", "")).replace("/", "\\")
        plan_dir = str(plan.get("generated_images_dir", "")).replace("/", "\\")
        if manifest_dir and manifest_dir != plan_dir:
            raise SystemExit("generated_images_manifest generated_images_dir mismatch")
    entries = {item.get("image_id"): item for item in manifest.get("items", manifest if isinstance(manifest, list) else [])}
    generated_dir = Path(plan["generated_images_dir"])
    failures = []
    checked = []
    for item in plan.get("items", []):
        image_id = item["image_id"]
        entry = entries.get(image_id)
        if not entry:
            failures.append({"image_id": image_id, "reason": "manifest_entry_missing"})
            continue
        path = generated_dir / item["output_filename"]
        if not path.exists():
            failures.append({"image_id": image_id, "reason": "image_file_missing"})
            continue
        digest = sha256(path)
        if entry.get("sha256") != digest:
            failures.append({"image_id": image_id, "reason": "sha256_mismatch"})
        if entry.get("filename") != item["output_filename"]:
            failures.append({"image_id": image_id, "reason": "filename_mismatch"})
        entry_path = Path(str(entry.get("path", ""))) if entry.get("path") else path
        try:
            resolved_entry_path = entry_path.resolve()
            resolved_generated_dir = generated_dir.resolve()
            if resolved_generated_dir not in [resolved_entry_path.parent, *resolved_entry_path.parents]:
                failures.append({"image_id": image_id, "reason": "manifest_path_not_in_generated_images_dir"})
        except Exception:
            pass
        if required_image2:
            if entry.get("declared_source") != "gpt_image_2":
                failures.append({"image_id": image_id, "reason": "declared_source_not_gpt_image_2"})
            if entry.get("created_by") != "image_2":
                failures.append({"image_id": image_id, "reason": "created_by_not_image_2"})
            if entry.get("generation_mode") != "gpt_image_2_only":
                failures.append({"image_id": image_id, "reason": "generation_mode_not_gpt_image_2_only"})
            if entry.get("manual_confirmed_source") is not True:
                failures.append({"image_id": image_id, "reason": "manual_confirmed_source_not_true"})
        width, height = image_size(path)
        checked.append({"image_id": image_id, "filename": path.name, "sha256": digest, "width": width, "height": height})
    report = {
        "required_gpt_image_2_only": required_image2,
        "valid": not failures,
        "failures": failures,
        "checked": checked,
    }
    write_json(workspace / "work" / "generated_images_manifest_audit.json", report)
    lines = ["# Generated Images Manifest Audit", "", f"- valid: {report['valid']}", f"- required_gpt_image_2_only: {required_image2}", ""]
    for failure in failures:
        lines.append(f"- {failure['image_id']}: {failure['reason']}")
    write_text(workspace / "work" / "generated_images_manifest_audit.md", "\n".join(lines) + "\n")
    if failures:
        raise SystemExit("generated images manifest validation failed")
    print(workspace / "work" / "generated_images_manifest_audit.md")


if __name__ == "__main__":
    main()
