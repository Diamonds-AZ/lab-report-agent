from pathlib import Path
import re
import sys

from docx import Document
from docx.enum.table import WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from docx.oxml.ns import qn
from utils.file_io import read_json, write_json, write_text
from utils.fs_safety import configure_utf8_stdio


EMU_PER_INCH = 914400
DEFAULT_IMAGE_WIDTH_INCHES = 5.2


def row_height_info(row):
    height = row.height
    rule = row.height_rule
    tr_pr = row._tr.get_or_add_trPr()
    tr_height = tr_pr.find(qn("w:trHeight"))
    return {
        "height_rule": getattr(rule, "name", str(rule)) if rule is not None else None,
        "height_inches": round(int(height) / EMU_PER_INCH, 3) if height is not None else None,
        "has_tr_height": tr_height is not None,
        "tr_height_rule": tr_height.get(qn("w:hRule")) if tr_height is not None else None,
        "tr_height_val": tr_height.get(qn("w:val")) if tr_height is not None else None,
    }


def allow_table_row_expand(row):
    before = row_height_info(row)
    row.height = None
    row.height_rule = WD_ROW_HEIGHT_RULE.AUTO
    tr_pr = row._tr.get_or_add_trPr()
    for tr_height in list(tr_pr.findall(qn("w:trHeight"))):
        tr_pr.remove(tr_height)
    after = row_height_info(row)
    return before, after


def image_dimensions(image_path: Path):
    try:
        from PIL import Image

        with Image.open(image_path) as img:
            return img.size
    except Exception:
        return None, None


def fit_image_size(image_path: Path, max_width_inches=DEFAULT_IMAGE_WIDTH_INCHES, max_height_inches=None):
    width_px, height_px = image_dimensions(image_path)
    inserted_width = max_width_inches
    inserted_height = None
    if width_px and height_px:
        inserted_height = inserted_width * (height_px / width_px)
        if max_height_inches and inserted_height > max_height_inches:
            scale = max_height_inches / inserted_height
            inserted_width *= scale
            inserted_height = max_height_inches
    return {
        "original_image_width": width_px,
        "original_image_height": height_px,
        "inserted_width_inches": round(inserted_width, 3),
        "inserted_height_inches": round(inserted_height, 3) if inserted_height else None,
    }


def clear_cell_keep_first_paragraph(cell, clear=True):
    if clear:
        cell.text = ""
    p = cell.paragraphs[0]
    if clear:
        p.clear()
    return p


def suspected_crop(before, after, fit):
    inserted_height = fit.get("inserted_height_inches")
    before_rule = before.get("height_rule")
    before_height = before.get("height_inches")
    after_rule = after.get("height_rule")
    fixed_before = before_rule == "EXACTLY" or before.get("tr_height_rule") == "exact"
    still_fixed = after_rule == "EXACTLY" or after.get("tr_height_rule") == "exact"
    if fixed_before and still_fixed:
        return True, "target row had fixed height and could not be changed to auto height"
    if fixed_before and before_height and inserted_height and before_height < inserted_height:
        return False, "target row had fixed height smaller than inserted image; row height was changed to auto"
    return False, None


def caption_for_item(number: int, item: dict) -> str:
    caption = str(item.get("caption") or "").strip()
    instruction_markers = ("画面不加", "不要添加", "不添加", "AI/示意图", "水印", "图号")
    if caption and any(marker in caption for marker in instruction_markers):
        caption = ""
    if not caption:
        caption = str(item.get("image_purpose") or item.get("purpose") or item.get("step_context") or item.get("image_item_id") or "图片").strip()
    caption = re.sub(r"^实施阶段第\s*[\d\s至到\-—]+\s*项[：:]\s*", "", caption)
    return f"图 {number} {caption}"


def add_image_to_cell(cell, row, image_path: Path, caption: str, item, clear=True):
    before, after = allow_table_row_expand(row)
    fit = fit_image_size(image_path)
    p = clear_cell_keep_first_paragraph(cell, clear=clear)
    if not clear:
        p = cell.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_together = True
    run = p.add_run()
    run.add_picture(str(image_path), width=Inches(fit["inserted_width_inches"]))
    p.add_run().add_break()
    caption_run = p.add_run(caption)
    caption_run.font.size = Pt(9)
    cropped, warning = suspected_crop(before, after, fit)
    return {
        "image_id": item.get("image_id"),
        "container_type": "table_cell",
        "target_table_index": item.get("target_table_index"),
        **fit,
        "row_height_rule_before": before.get("height_rule"),
        "row_height_rule_after": after.get("height_rule"),
        "row_height_before": before,
        "row_height_after": after,
        "suspected_cropped": cropped,
        "layout_warning": warning,
    }


def paragraph_index(block_id):
    match = re.fullmatch(r"p(\d+)", str(block_id or ""))
    return int(match.group(1)) if match else None


def clear_paragraph(paragraph):
    paragraph.clear()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT


def delete_paragraph(paragraph):
    element = paragraph._element
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def paragraph_is_blank(paragraph):
    return not (paragraph.text or "").strip()


def add_image_to_paragraph_region(doc, item, image_path: Path, caption: str):
    anchor = item.get("target_anchor")
    block_range = item.get("target_block_range") or []
    if not anchor:
        raise ValueError("paragraph_blank_region missing target_anchor")
    if len(block_range) != 2:
        raise ValueError("paragraph_blank_region requires target_block_range with start and end block ids")

    start_idx = paragraph_index(block_range[0])
    end_idx = paragraph_index(block_range[1])
    if start_idx is None or end_idx is None or start_idx > end_idx:
        raise ValueError(f"invalid target_block_range: {block_range}")
    if end_idx >= len(doc.paragraphs):
        raise ValueError(f"target_block_range out of bounds: {block_range}")

    anchor_idx = None
    for idx, paragraph in enumerate(doc.paragraphs[: start_idx + 1]):
        if anchor in paragraph.text:
            anchor_idx = idx
    if anchor_idx is None:
        raise ValueError(f"target_anchor not found before region: {anchor}")

    region = doc.paragraphs[start_idx : end_idx + 1]
    if not region:
        raise ValueError(f"empty paragraph region: {block_range}")
    if not any(paragraph_is_blank(p) for p in region):
        raise ValueError(f"target_block_range has no blank paragraph: {block_range}")

    image_paragraph = region[0]
    clear_paragraph(image_paragraph)
    image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    image_paragraph.paragraph_format.keep_together = True
    fit = fit_image_size(image_path)
    image_paragraph.add_run().add_picture(str(image_path), width=Inches(fit["inserted_width_inches"]))
    image_paragraph.add_run().add_break()
    caption_run = image_paragraph.add_run(caption)
    caption_run.font.size = Pt(9)

    for paragraph in reversed(region[1:]):
        delete_paragraph(paragraph)

    return {
        "image_id": item.get("image_id"),
        "container_type": "paragraph_blank_region",
        "target_anchor": item.get("target_anchor"),
        "target_block_range": item.get("target_block_range"),
        **fit,
        "row_height_rule_before": None,
        "row_height_rule_after": None,
        "suspected_cropped": False,
        "layout_warning": None,
    }


def quality_warning_for_image(image_path: Path, item):
    file_size = image_path.stat().st_size if image_path.exists() else 0
    record = {
        "image_id": item.get("image_id"),
        "image_source": item.get("image_source", "unknown"),
        "filename": image_path.name,
        "file_size": file_size,
        "width": None,
        "height": None,
        "mean_brightness": None,
        "brightness_std": None,
        "unique_color_sample": None,
        "suspected_low_information": False,
        "warning": None,
    }
    warnings = []
    if file_size < 20000:
        warnings.append("file is unusually small")
    try:
        from PIL import Image, ImageStat

        with Image.open(image_path) as img:
            record["width"], record["height"] = img.size
            if img.width < 400 or img.height < 300:
                warnings.append("image resolution is unusually low")
            sample = img.convert("RGB").resize((96, 96))
            gray = sample.convert("L")
            stat = ImageStat.Stat(gray)
            mean = float(stat.mean[0])
            std = float(stat.stddev[0])
            record["mean_brightness"] = round(mean, 2)
            record["brightness_std"] = round(std, 2)
            colors = sample.getcolors(maxcolors=9216) or []
            record["unique_color_sample"] = len(colors)
            low_information = std < 2.0 and len(colors) <= 16
            almost_black = mean < 8 and std < 2.0 and len(colors) <= 16
            almost_white = mean > 247 and std < 2.0 and len(colors) <= 16
            if almost_black:
                warnings.append("image appears almost black and has very little visual variation")
            elif almost_white:
                warnings.append("image appears almost white and has very little visual variation")
            elif low_information:
                warnings.append("image has very little visual variation")
            record["suspected_low_information"] = bool(low_information or almost_black or almost_white)
    except Exception as exc:
        warnings.append(f"quality_check_failed:{exc}")
    record["warning"] = "; ".join(warnings) if warnings else None
    return record


def load_plan(workspace: Path):
    current_run_path = workspace / "work" / "current_run.json"
    if not current_run_path.exists():
        raise RuntimeError("Missing work/current_run.json; run pre_images before inserting images.")
    current_run = read_json(current_run_path)
    plan_path = Path(current_run["image_generation_plan"])
    if not plan_path.is_absolute():
        plan_path = workspace / plan_path
    if not plan_path.exists():
        raise RuntimeError(f"Missing image generation plan: {plan_path}")
    work_plan_path = workspace / "work" / "image_generation_plan.json"
    if not work_plan_path.exists():
        raise RuntimeError("Missing work/image_generation_plan.json.")
    plan = read_json(plan_path)
    work_plan = read_json(work_plan_path)
    if work_plan.get("run_id") != plan.get("run_id"):
        raise RuntimeError("Run ID mismatch between run image_generation_plan.json and work/image_generation_plan.json.")
    if plan.get("run_id") != current_run.get("run_id"):
        raise RuntimeError("Run ID mismatch between current_run.json and image_generation_plan.json.")
    if str(plan.get("generated_images_dir")) != str(current_run.get("generated_images_dir")):
        raise RuntimeError("generated_images_dir mismatch between current_run.json and image_generation_plan.json.")
    plan_dir = Path(plan.get("generated_images_dir", ""))
    if plan_dir.name != "generated_images" or plan_dir.parent.name != plan["run_id"]:
        raise RuntimeError("generated_images_dir is not inside the current work/runs/<run_id>/ directory.")
    return plan


def image_path_for_item(generated_dir: Path, item):
    path = generated_dir / item["output_filename"]
    if not path.exists():
        raise RuntimeError(f"Missing generated image for {item['image_id']}: {path}")
    return path


def unresolved_item(item, reason):
    return {
        "image_id": item.get("image_id"),
        "image_item_id": item.get("image_item_id"),
        "image_source": item.get("image_source", "unknown"),
        "reason": reason,
        "target_anchor": item.get("target_anchor"),
        "target_block_range": item.get("target_block_range"),
        "layout_type": item.get("layout_type"),
        "zone_type": item.get("zone_type"),
    }


def forbidden_zone(item):
    zone = item.get("zone_type")
    if zone in ("question_area", "reference_material") and not item.get("explicitly_allowed_question_area_image"):
        return f"forbidden_image_zone:{zone}"
    if not zone:
        return "missing_zone_type"
    return None


def main():
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    report = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "output" / "reports" / "流程测试_实验报告.docx"
    if not report.is_absolute():
        report = workspace / report

    plan = load_plan(workspace)
    generated_dir = Path(plan["generated_images_dir"])
    if not generated_dir.is_absolute():
        generated_dir = workspace / generated_dir
    image_list = Path(plan["run_dir"]) / "image_list.md"
    audit = Path(plan["run_dir"]) / "image_insert_audit.json"
    quality_audit_path = Path(plan["run_dir"]) / "image_quality_audit.json"

    doc = Document(report)
    items = plan.get("items", [])
    expected = int(plan.get("expected_image_count", len(items)))
    if len(items) != expected:
        raise RuntimeError(f"Image plan mismatch: expected {expected}, got {len(items)} items.")

    expected_filenames = {item["output_filename"] for item in items}
    generated_files = sorted(p.name for p in generated_dir.glob("*.png") if p.is_file()) if generated_dir.exists() else []
    missing = [item for item in items if not (generated_dir / item["output_filename"]).exists()]
    unexpected = [name for name in generated_files if name not in expected_filenames]
    generated_expected_count = len(expected_filenames) - len(missing)
    if missing:
        ids = ", ".join(item["image_id"] for item in missing)
        write_json(
            audit,
            {
                "report": str(report),
                "run_id": plan["run_id"],
                "generated_images_dir": str(generated_dir),
                "legacy_image_used": False,
                "expected_image_count": expected,
                "generated_image_count": generated_expected_count,
                "inserted_image_count": 0,
                "missing_images": [
                    {"image_id": item["image_id"], "output_filename": item["output_filename"], "image_source": item.get("image_source", "unknown")}
                    for item in missing
                ],
                "unexpected_images": unexpected,
                "unresolved_image_count": 0,
                "unresolved_image": [],
                "inserted": [],
            },
        )
        raise RuntimeError(f"Generated images missing from current run directory for: {ids}. Do not use legacy images.")

    inserted = []
    unresolved_image = []
    layout_audit = []
    quality_audit = []

    for n, item in enumerate(items, 1):
        zone_error = forbidden_zone(item)
        if zone_error:
            unresolved_image.append(unresolved_item(item, zone_error))
            continue
        table_index = item.get("target_table_index")
        row_index = item.get("target_row_index")
        cell_index = item.get("target_cell_index")
        layout_type = item.get("layout_type")
        image = image_path_for_item(generated_dir, item)
        quality_audit.append(quality_warning_for_image(image, item))
        caption = caption_for_item(n, item)
        if table_index is None:
            if layout_type == "paragraph_blank_region":
                try:
                    layout = add_image_to_paragraph_region(doc, item, image, caption)
                    layout_audit.append(layout)
                    inserted.append(
                        {
                            "image_id": item["image_id"],
                            "image_source": item.get("image_source", "unknown"),
                            "layout_type": layout_type,
                            "target_anchor": item.get("target_anchor"),
                            "target_block_range": item.get("target_block_range"),
                            "image": str(image),
                            "caption": caption,
                            "layout": layout,
                        }
                    )
                except Exception as exc:
                    unresolved_image.append(unresolved_item(item, f"paragraph_blank_region_failed:{exc}"))
                continue
            unresolved_image.append(unresolved_item(item, "unsupported_non_table_image_slot"))
            continue
        if table_index < 0 or table_index >= len(doc.tables):
            unresolved_image.append(unresolved_item(item, f"invalid_target_table_index:{table_index}"))
            continue
        table = doc.tables[table_index]
        row_index = int(row_index if row_index is not None else 0)
        cell_index = int(cell_index if cell_index is not None else 0)
        if row_index < 0 or row_index >= len(table.rows):
            unresolved_image.append(unresolved_item(item, f"invalid_target_row_index:{row_index}"))
            continue
        if cell_index < 0 or cell_index >= len(table.rows[row_index].cells):
            unresolved_image.append(unresolved_item(item, f"invalid_target_cell_index:{cell_index}"))
            continue
        clear_cell = layout_type != "table_cell_append"
        layout = add_image_to_cell(table.cell(row_index, cell_index), table.rows[row_index], image, caption, item, clear=clear_cell)
        layout_audit.append(layout)
        inserted.append({"image_id": item["image_id"], "image_source": item.get("image_source", "unknown"), "table_index": table_index, "row_index": row_index, "cell_index": cell_index, "layout_type": layout_type or "table_cell", "image": str(image), "caption": caption, "layout": layout})

    doc.save(report)
    quality_warnings = [item for item in quality_audit if item.get("warning")]
    layout_warnings = [item for item in layout_audit if item.get("layout_warning")]
    write_json(
        audit,
        {
            "report": str(report),
            "run_id": plan["run_id"],
            "generated_images_dir": str(generated_dir),
            "legacy_image_used": False,
            "expected_image_count": expected,
            "generated_image_count": generated_expected_count,
            "inserted_image_count": len(inserted),
            "missing_images": [],
            "unexpected_images": unexpected,
            "unresolved_image_count": len(unresolved_image),
            "unresolved_image": unresolved_image,
            "layout_audit": layout_audit,
            "suspected_cropped_images": [item for item in layout_audit if item.get("suspected_cropped")],
            "image_layout_warnings": layout_warnings,
            "image_quality_warning_count": len(quality_warnings),
            "image_quality_warnings": quality_warnings,
            "inserted": inserted,
        },
    )
    write_json(quality_audit_path, {"run_id": plan["run_id"], "items": quality_audit, "warnings": quality_warnings})

    lines = ["# 图片清单", "", "| 编号 | 目标 | 图片路径 | 插入状态 | 质量预警 |", "|---|---|---|---|---|"]
    for item in items:
        image = generated_dir / item["output_filename"]
        if any(x["image_id"] == item["image_id"] for x in inserted):
            status = "inserted"
        elif any(x["image_id"] == item["image_id"] for x in unresolved_image):
            status = "unresolved_unsupported_slot"
        else:
            status = "not_inserted"
        target = item.get("target_table_index")
        if target is None:
            target = item.get("layout_type") or item.get("target_anchor") or ""
        q = next((x for x in quality_audit if x["image_id"] == item["image_id"]), {})
        lines.append(f"| {item['image_id']} | {target} | `{image}` | {status} | {q.get('warning') or ''} |")
    if unresolved_image:
        lines.extend(["", "## 未插入图片位", ""])
        for item in unresolved_image:
            lines.append(f"- `{item['image_id']}`: {item['reason']}。已预留 target_anchor / target_block_range / layout_type 接口，当前版本不乱插。")
    write_text(image_list, "\n".join(lines) + "\n")
    write_text(workspace / "work" / "image_list.md", "\n".join(lines) + "\n")
    print(report)
    print(audit)


if __name__ == "__main__":
    main()
