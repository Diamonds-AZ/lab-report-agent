from __future__ import annotations

from pathlib import Path
import sys

from utils.file_io import read_json, write_text
from utils.fs_safety import configure_utf8_stdio


PENDING_VALUES = {"pending_gpt_semantic_judgment", "needs_gpt_semantic_judgment", ""}


LABELS = {
    "task_goal": {
        "complete_lab_report": "完成整份实验报告",
        "fill_blanks_only": "只填写空白",
        "polish_only": "只润色已有内容",
        "image_replace_only": "只处理图片",
        "analyze_only": "只分析，不生成报告",
    },
    "experiment_type": {
        "database_datagrip": "数据库 / DataGrip / MySQL 类实验",
        "network_hcl": "网络 / HCL / 路由交换类实验",
        "java_idea": "Java / IntelliJ IDEA 类实验",
        "web_vscode": "Web / VS Code 类实验",
        "linux_terminal": "Linux / 终端命令类实验",
        "python_script": "Python 脚本类实验",
        "c_data_structure": "C 语言 / 数据结构类实验",
        "mcu_keil_aiot": "单片机 / Keil / AIoT 类实验",
        "generic_report": "通用实验报告",
    },
    "document_pattern": {
        "blank_fill_template": "模板里有明确空白，需要按空白填写",
        "per_requirement_template": "按题目/编号任务逐项完成",
        "full_report_template": "需要补全完整报告内容",
        "image_table_template": "以截图表格/图片区为主",
        "mixed_template": "文字填写和图片插入混合",
        "unknown": "暂不确定",
    },
    "writing_mode": {
        "fill_blanks": "按空白填写",
        "full_report": "补全完整报告",
        "per_requirement": "按编号任务逐项写",
        "polish_only": "只润色",
        "image_replace_only": "只替换/补图片",
    },
    "coverage_mode": {
        "strict": "严格覆盖：题目、编号任务、截图要求都要逐项处理",
        "normal": "正常覆盖：重点内容都要处理，允许少量合并",
        "loose": "宽松覆盖：只补主要内容",
    },
    "detail_level": {
        "brief": "简略",
        "normal": "正常",
        "complete": "完整",
        "verbose": "详细",
    },
    "image_mode": {
        "gpt_image_2_only": "必须使用 image-2 生成图片",
        "user_provided_only": "只使用用户提供的图片",
        "real_screenshot_only": "只使用真实软件截图",
        "script_reference": "允许脚本参考图",
        "none": "不需要图片",
        "user_provided_or_confirmed": "图片来源需要用户确认",
    },
    "identity_policy": {
        "skip_identity_fields": "不新增姓名、学号、班级等个人信息",
        "preserve_existing_identity": "保留模板里已有的个人信息，不新增",
        "clear_identity_fields": "清空模板里已有的姓名、学号、班级等个人信息",
        "fill_identity_fields": "按用户提供的信息填写个人信息",
        "preserve_existing": "保留已有信息，不凭空补个人信息",
    },
    "format_policy": {
        "preserve_template": "尽量保持原 Word 模板格式",
        "allow_minor_adjustment": "允许少量排版调整",
    },
}


def field_value(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    if isinstance(value, dict):
        value = value.get("value", default)
    return str(value or default)


def field_obj(data: dict, key: str) -> dict:
    value = data.get(key)
    if isinstance(value, dict):
        return value
    return {"value": value or "", "confidence": None, "evidence": [], "reason": ""}


def human_label(key: str, value: str) -> str:
    return LABELS.get(key, {}).get(value, value or "待判断")


def confidence_text(value) -> str:
    if value is None:
        return "未标注"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def clean_text(value, fallback: str = "暂无") -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("\n", " ").split())
    return text or fallback


def bullet_list(values, fallback: str = "暂无明确证据") -> list[str]:
    if isinstance(values, str):
        values = [values]
    items = [clean_text(v, "") for v in values or []]
    items = [item for item in items if item]
    if not items:
        items = [fallback]
    return [f"- {item}" for item in items[:8]]


def load_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    data = read_json(path)
    return data if isinstance(data, dict) else {}


def load_requirements(workspace: Path, packet: dict) -> list[str]:
    path = workspace / "work" / "requirement_items.json"
    items: list[str] = []
    if path.exists():
        data = read_json(path)
        raw_items = data.get("items") if isinstance(data, dict) else data
        for item in raw_items or []:
            rid = item.get("requirement_id") or item.get("id") or f"REQ-{len(items) + 1:03d}"
            text = item.get("original_text") or item.get("text") or item.get("nearby_context") or ""
            text = clean_text(text, "")
            if text:
                items.append(f"{rid}: {text[:120]}")
            if len(items) >= 10:
                break
    if not items:
        for text in packet.get("numbered_requirement_preview") or []:
            cleaned = clean_text(text, "")
            if cleaned:
                items.append(cleaned[:140])
            if len(items) >= 10:
                break
    return items


def field_section(title: str, key: str, directives: dict, plain_hint: str) -> list[str]:
    obj = field_obj(directives, key)
    value = clean_text(obj.get("value"), "待判断")
    is_pending = value in PENDING_VALUES
    lines = [
        f"## {title}",
        "",
        f"- 识别结果：**{human_label(key, value)}**" if not is_pending else "- 识别结果：**待 Codex/GPT 语义判断**",
        f"- 内部代号：`{value}`",
        f"- 可信度：{confidence_text(obj.get('confidence'))}",
        f"- 这意味着：{plain_hint if not is_pending else '目前还不能继续，需要先由 Codex/GPT 根据 Word 内容做语义判断。'}",
        "",
        "依据：",
    ]
    lines.extend(bullet_list(obj.get("evidence")))
    reason = clean_text(obj.get("reason"), "")
    if reason:
        lines.extend(["", f"判断理由：{reason}"])
    lines.append("")
    return lines


def render(workspace: Path) -> str:
    directives_path = workspace / "work" / "auto_task_directives.json"
    if not directives_path.exists():
        directives_path = workspace / "work" / "task_directives.json"
    if not directives_path.exists():
        raise SystemExit("Missing work/auto_task_directives.json or work/task_directives.json")
    directives = read_json(directives_path)
    packet = load_json_if_exists(workspace / "work" / "semantic_task_judgment_packet.json")
    requirements = load_requirements(workspace, packet)
    task_name = packet.get("task_name") or field_value(directives, "task_name", "本次实验报告")
    input_report = packet.get("input_report") or ""
    confirmed = bool(directives.get("confirmed_by_user"))

    lines = [
        "# 第一阶段确认：请检查我对实验报告的理解",
        "",
        "这一步只确认“方向是否正确”，还不会生成最终 Word，也不会生成或插入图片。",
        "请像检查外卖订单一样看一遍：实验类型、填写方式、图片来源、个人信息处理是否符合你的想法。",
        "",
        "## 本次任务",
        "",
        f"- 报告名称：{clean_text(task_name, '未命名实验报告')}",
        f"- 模板文件：`{clean_text(input_report, '未记录')}`",
        f"- 当前状态：{'已确认' if confirmed else '等待你确认'}",
        "",
    ]
    lines.extend(
        field_section(
            "1. 我要做什么",
            "task_goal",
            directives,
            "我会把这份模板当作要完成的实验报告来处理，而不是只做分析。",
        )
    )
    lines.extend(
        field_section(
            "2. 实验属于哪一类",
            "experiment_type",
            directives,
            "这只表示实验领域/软件环境，不会强行决定报告该怎么写。",
        )
    )
    lines.extend(
        field_section(
            "3. Word 模板长什么样",
            "document_pattern",
            directives,
            "这表示模板结构，例如是填空、逐项任务、图片区表格，还是混合型。",
        )
    )
    lines.extend(
        field_section(
            "4. 报告应该怎么写",
            "writing_mode",
            directives,
            "后续正文会按这个方式生成，例如逐项覆盖题目，或只补空白。",
        )
    )
    lines.extend(
        field_section(
            "5. 覆盖详细程度",
            "coverage_mode",
            directives,
            "它决定是否必须逐条覆盖模板里的任务和截图要求。",
        )
    )
    lines.extend(
        field_section(
            "6. 内容详细程度",
            "detail_level",
            directives,
            "它决定正文是简短、正常、完整还是更详细。",
        )
    )
    lines.extend(
        field_section(
            "7. 图片来源策略",
            "image_mode",
            directives,
            "如果这里是 image-2，则后续图片必须调用 image-2，不能用脚本图、旧图或占位图替代。",
        )
    )
    lines.extend(
        field_section(
            "8. 姓名学号等个人信息",
            "identity_policy",
            directives,
            "它决定是否保留、清空或填写姓名、学号、班级等身份字段。",
        )
    )
    lines.extend(
        field_section(
            "9. Word 格式处理",
            "format_policy",
            directives,
            "默认尽量保持模板原来的表格、段落和排版。",
        )
    )
    lines.extend(["## 我准备覆盖的主要内容", ""])
    if requirements:
        lines.extend(f"- {item}" for item in requirements)
    else:
        lines.append("- 还没有提取到清晰的编号任务；后续会按模板栏目继续语义判断。")
    lines.extend(["", "## 需要你重点看一眼", ""])
    image_mode = field_value(directives, "image_mode")
    if image_mode == "gpt_image_2_only":
        lines.append("- 图片策略是 **必须使用 image-2**：确认后也不能用脚本模拟图、旧图、占位图替代。")
    else:
        lines.append("- 图片来源还不是 image-2 硬约束；如果你想强制 image-2，请直接说“截图必须用 image-2”。")
    if any(field_value(directives, key) in PENDING_VALUES for key in ("experiment_type", "document_pattern", "writing_mode", "coverage_mode", "detail_level")):
        lines.append("- 仍有项目处于“待语义判断”状态，Codex/GPT 需要先补完整再让你确认。")
    if field_value(directives, "identity_policy") in {"skip_identity_fields", "preserve_existing_identity", "clear_identity_fields"}:
        lines.append("- 我不会凭空新增姓名、学号、班级等个人信息。")
    lines.extend(
        [
            "",
            "## 你可以怎么回复",
            "",
            "- 如果都对，回复：**确认继续**",
            "- 如果有不对，直接说哪里要改，例如：",
            "  - “不是网络实验，是 Keil/AIoT 实验。”",
            "  - “不要按编号逐项写，只填模板空白。”",
            "  - “图片必须全部用 image-2。”",
            "  - “保留模板里已有的姓名学号，不要清空。”",
            "",
            "只要你提出修改，我会更新这份理解结果，然后重新发这一页让你确认。你确认前不会进入下一阶段。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    out = workspace / "work" / "task_understanding_confirmation.md"
    write_text(out, render(workspace))
    print(out)


if __name__ == "__main__":
    main()
