from __future__ import annotations

from pathlib import Path
import re
import sys

from utils.file_io import read_json, write_text
from utils.fs_safety import configure_utf8_stdio


def clean_cell(value, fallback: str = "待确认") -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("\n", " ").split())
    if not text:
        return fallback
    if "�" in text or re.search(r"\?{3,}", text):
        return fallback
    return text.replace("|", "\\|")


def short_join(values, fallback: str = "待确认") -> str:
    if not values:
        return fallback
    if isinstance(values, str):
        return clean_cell(values, fallback)
    return "<br>".join(clean_cell(v, fallback) for v in values if clean_cell(v, "")).strip() or fallback


def yes_no(value: bool) -> str:
    return "是" if value else "否"


def human_source_policy(value: str) -> str:
    mapping = {
        "gpt_image_2_only": "必须使用 image-2",
        "gpt_image_2": "image-2 生成",
        "manual_provided": "用户提供图片",
        "real_screenshot": "真实软件截图",
        "script_reference": "允许脚本参考图",
        "unknown": "待确认",
    }
    return mapping.get(value or "", value or "待确认")


def directives_value(directives: dict, key: str, default: str = "unknown") -> str:
    value = directives.get(key, default)
    if isinstance(value, dict):
        return value.get("value", default)
    return value or default


def load_requirement_map(workspace: Path) -> dict[str, str]:
    path = workspace / "work" / "requirement_items.json"
    if not path.exists():
        return {}
    data = read_json(path)
    items = data.get("items") if isinstance(data, dict) else data
    result = {}
    for item in items or []:
        rid = item.get("requirement_id") or item.get("id")
        if rid:
            result[rid] = clean_cell(item.get("original_text") or item.get("text") or rid)
    return result


def covered_requirements(item: dict, requirement_map: dict[str, str]) -> str:
    ids = item.get("covered_requirement_ids") or item.get("requirement_ids") or []
    if not ids:
        return "未标注，需要确认"
    cells = []
    for rid in ids:
        text = requirement_map.get(rid)
        if text:
            cells.append(f"{rid}: {text[:70]}")
        else:
            cells.append(str(rid))
    return "<br>".join(cells)


def human_position(item: dict) -> str:
    section = clean_cell(item.get("target_section"), "")
    anchor = clean_cell(
        item.get("nearby_anchor")
        or item.get("insert_after_text")
        or item.get("target_anchor")
        or item.get("step_context"),
        "",
    )
    table_index = item.get("target_table_index")
    row_index = item.get("target_row_index")
    cell_index = item.get("target_cell_index")
    layout_type = item.get("layout_type")

    parts: list[str] = []
    if section:
        parts.append(f"栏目“{section}”")
    if table_index is not None:
        table_desc = f"第 {int(table_index) + 1} 个表格"
        if row_index is not None:
            table_desc += f"，第 {int(row_index) + 1} 行"
        if cell_index is not None:
            table_desc += f"，第 {int(cell_index) + 1} 列"
        parts.append(table_desc)
    elif layout_type == "paragraph_blank_region":
        parts.append("段落空白区")
    elif layout_type:
        parts.append(clean_cell(layout_type))
    if anchor:
        parts.append(f"在“{anchor[:80]}”附近或之后")
    return "；".join(parts) if parts else "待确认"


def must_show_summary(item: dict) -> str:
    pieces: list[str] = []
    code = item.get("must_show_code_or_sql") or item.get("must_show_commands") or item.get("must_show_code")
    result = item.get("must_show_result")
    message = item.get("must_show_error_or_success_message")
    if code:
        pieces.append("代码/命令/SQL：" + short_join(code))
    if result:
        pieces.append("结果：" + short_join(result))
    if message:
        pieces.append("成功/错误信息：" + short_join(message))
    return "<br>".join(pieces) if pieces else "按图片内容说明展示"


def content_summary(item: dict) -> str:
    values = [
        item.get("image_purpose"),
        item.get("caption"),
        item.get("step_context"),
        item.get("prompt_topic"),
    ]
    for value in values:
        cleaned = clean_cell(value, "")
        if cleaned:
            return cleaned
    return "待确认"


def item_warning(item: dict, source_policy: str) -> str:
    warnings: list[str] = []
    joined = " ".join(str(v) for v in item.values())
    if "�" in joined or re.search(r"\?{3,}", joined):
        warnings.append("存在疑似乱码字段，需以 Word 原文锚点复核")
    if item.get("zone_type") in ("question_area", "reference_material"):
        warnings.append("目标区域疑似题目/参考材料区，默认禁止插图，除非用户明确要求")
    if not item.get("zone_type"):
        warnings.append("缺少 zone_type，无法判断是否为作答区")
    if source_policy == "gpt_image_2_only" and item.get("image_source") not in (None, "gpt_image_2", "unknown"):
        warnings.append("图片来源字段与 image-2 硬约束不一致")
    return "<br>".join(warnings) if warnings else "无"


def skipped_or_forbidden_summary(plan: dict) -> list[str]:
    lines: list[str] = []
    for item in plan.get("items", []):
        if item.get("is_image_required"):
            continue
        zone = item.get("zone_type")
        reason = item.get("skip_reason") or item.get("reason") or item.get("unresolved_reason")
        anchor = item.get("nearby_anchor") or item.get("insert_after_text") or item.get("target_anchor")
        if zone in ("question_area", "reference_material", "identity_area") or reason:
            text = clean_cell(anchor or item.get("caption") or item.get("image_purpose"), "未标注位置")
            why = clean_cell(reason or f"{zone} 默认不插图", "默认不插图")
            lines.append(f"- {text}：{why}")
    return lines[:8]


def main() -> None:
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    plan_path = workspace / "work" / "refined_image_plan.json"
    if not plan_path.exists():
        raise SystemExit("Missing work/refined_image_plan.json")
    plan = read_json(plan_path)
    directives_path = workspace / "work" / "task_directives.json"
    directives = read_json(directives_path) if directives_path.exists() else {}
    image_mode = directives_value(directives, "image_mode", "unknown")
    requirement_map = load_requirement_map(workspace)
    required = [item for item in plan.get("items", []) if item.get("is_image_required")]

    lines = [
        "# 第二阶段确认：请检查图片要放在哪里、图片里要画什么",
        "",
        "这一步只确认图片方案。你确认前，我不会生成图片，也不会把图片插入 Word。",
        "请重点看三件事：图片数量对不对、位置对不对、图片内容能不能说明实验结果。",
        "",
        "## 图片方案总览",
        "",
        f"- 计划图片数：{len(required)}",
        f"- 当前图片策略：**{human_source_policy(image_mode)}**（内部代号：`{image_mode}`）",
        f"- 当前状态：{'已确认' if bool(plan.get('confirmed_by_user')) else '等待你确认'}",
        "",
        "## 图片清单",
        "",
        "| 图片 | 区域类型 | 放在哪里 | 附近文字/锚点 | 覆盖哪些要求 | 图片里会展示什么 | 必须展示的细节 | 来源策略 | 必须 image-2 | 备注/风险 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for idx, item in enumerate(required, 1):
        source_policy = item.get("image_source_policy") or image_mode
        anchor = clean_cell(
            item.get("nearby_anchor")
            or item.get("insert_after_text")
            or item.get("target_anchor")
            or item.get("step_context"),
            "待确认",
        )
        must_image2 = source_policy == "gpt_image_2_only" or image_mode == "gpt_image_2_only"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"图 {idx}",
                    clean_cell(item.get("zone_type"), "缺失，需补充"),
                    human_position(item),
                    anchor,
                    covered_requirements(item, requirement_map),
                    content_summary(item),
                    must_show_summary(item),
                    human_source_policy(clean_cell(source_policy, "unknown")),
                    yes_no(must_image2),
                    item_warning(item, source_policy),
                ]
            )
            + " |"
        )
    forbidden = skipped_or_forbidden_summary(plan)
    lines.extend(["", "## 明确不会插图的位置", ""])
    if forbidden:
        lines.extend(forbidden)
    else:
        lines.append("- 暂无额外记录。默认不会把图片插入题目说明区、参考材料区、姓名学号区域。")
    lines.extend(
        [
            "",
            "## 你可以怎么回复",
            "",
            "- 如果都对，回复：**确认继续**",
            "- 如果某张图不对，直接说图几要怎么改，例如：",
            "  - “图 1 放错了，应该放到实验结果表格里。”",
            "  - “图 2 不要拓扑图，改成 ping 测试结果。”",
            "  - “少了一张路由表截图，补到第 3 张。”",
            "- 只要你提出修改，我会更新图片方案，然后重新发这一张表让你确认。",
            "- 如果图片策略是 **必须使用 image-2**，确认后仍只能调用 image-2，不能用脚本图、占位图或旧图替代。",
            "",
        ]
    )
    write_text(workspace / "work" / "image_insertion_confirmation.md", "\n".join(lines))
    print(workspace / "work" / "image_insertion_confirmation.md")


if __name__ == "__main__":
    main()
