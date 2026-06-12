from __future__ import annotations

from pathlib import Path
import re
import sys

from docx import Document

from utils.confirmation import infer_confirmation_mode
from utils.file_io import read_json, write_json, write_text
from utils.fs_safety import configure_utf8_stdio
from render_task_confirmation import render as render_task_confirmation


PENDING = "pending_gpt_semantic_judgment"


def doc_text(path: Path) -> str:
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    parts.extend(
        cell.text
        for table in doc.tables
        for row in table.rows
        for cell in row.cells
        if cell.text.strip()
    )
    return "\n".join(parts)


def field(value: str, confidence: float, evidence: list[str], reason: str) -> dict:
    return {
        "value": value,
        "confidence": round(float(confidence), 2),
        "evidence": evidence[:12],
        "reason": reason,
    }


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def task_yaml_text(workspace: Path) -> str:
    return read_text_if_exists(workspace / "configs" / "task.yaml")


def yaml_scalar(text: str, key: str) -> str | None:
    pattern = rf"(?m)^\s*{re.escape(key)}\s*:\s*['\"]?([^'\"\n#]+)['\"]?\s*(?:#.*)?$"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def yaml_bool_under(text: str, parent: str, key: str) -> bool | None:
    parent_match = re.search(rf"(?m)^\s*{re.escape(parent)}\s*:\s*$", text)
    if not parent_match:
        return None
    start = parent_match.end()
    following = text[start:]
    block_lines: list[str] = []
    for line in following.splitlines():
        if line.strip() and not line.startswith((" ", "\t")):
            break
        block_lines.append(line)
    block = "\n".join(block_lines)
    match = re.search(rf"(?m)^\s+{re.escape(key)}\s*:\s*(true|false|yes|no|0|1)\s*$", block, re.I)
    if not match:
        return None
    return match.group(1).lower() in {"true", "yes", "1"}


def yaml_scalar_under(text: str, parent: str, key: str) -> str | None:
    parent_match = re.search(rf"(?m)^\s*{re.escape(parent)}\s*:\s*$", text)
    if not parent_match:
        return None
    start = parent_match.end()
    following = text[start:]
    block_lines: list[str] = []
    for line in following.splitlines():
        if line.strip() and not line.startswith((" ", "\t")):
            break
        block_lines.append(line)
    block = "\n".join(block_lines)
    match = re.search(rf"(?m)^\s+{re.escape(key)}\s*:\s*['\"]?([^'\"\n#]+)['\"]?\s*(?:#.*)?$", block)
    return match.group(1).strip() if match else None


def likely_user_image_mode(user_text: str, config_text: str) -> dict:
    combined = f"{user_text}\n{config_text}".lower()
    configured = yaml_scalar(config_text, "image_mode") or yaml_scalar(config_text, "image_source_policy")
    if configured:
        return field(
            configured,
            1.0,
            [f"configs/task.yaml explicitly sets image mode to {configured}"],
            "This is a task constraint, not an experiment-type guess.",
        )
    if any(token in combined for token in ("image-2", "image 2", "gpt-image", "gpt_image", "gpt image")):
        return field(
            "gpt_image_2_only",
            1.0,
            ["User request mentions image-2 / GPT-image."],
            "Final inserted images must come from image-2; script or placeholder images are forbidden.",
        )
    if "真实截图" in combined or "real screenshot" in combined:
        return field("real_screenshot_only", 0.95, ["User requested real screenshots."], "Use only real screenshots.")
    if "不需要图片" in combined or "不用图片" in combined or "no image" in combined:
        return field("none", 0.95, ["User requested no images."], "No image generation is needed.")
    return field(
        "user_provided_or_confirmed",
        0.55,
        ["No hard image-source constraint was found in user text or task.yaml."],
        "Image source must be confirmed before image generation or insertion.",
    )


def likely_identity_policy(user_text: str, config_text: str) -> dict:
    configured_policy = yaml_scalar_under(config_text, "identity_rules", "identity_policy") or yaml_scalar(config_text, "identity_policy")
    if configured_policy:
        return field(
            configured_policy,
            1.0,
            [f"configs/task.yaml sets identity_rules.identity_policy={configured_policy}."],
            "Use the explicit identity policy from task initialization.",
        )
    clear_identity = yaml_bool_under(config_text, "identity_rules", "clear_identity_fields")
    if clear_identity is True:
        return field(
            "clear_identity_fields",
            1.0,
            ["configs/task.yaml sets identity_rules.clear_identity_fields=true."],
            "Existing name, student ID, class, and similar identity fields should be cleared.",
        )
    fill_identity = yaml_bool_under(config_text, "identity_rules", "fill_identity_fields")
    if fill_identity is False:
        return field(
            "preserve_existing_identity",
            1.0,
            ["configs/task.yaml sets identity_rules.fill_identity_fields=false."],
            "Do not add new identity information; preserve existing template identity text unless clear_identity_fields=true.",
        )
    if fill_identity is True:
        return field(
            "fill_identity_fields",
            1.0,
            ["configs/task.yaml sets identity_rules.fill_identity_fields=true."],
            "Identity fields may be filled if values are available.",
        )
    if any(token in user_text for token in ("不填姓名", "不填写姓名", "不填学号", "不填写学号", "不要填写个人信息", "不填个人信息")):
        return field(
            "skip_identity_fields",
            1.0,
            ["User explicitly requested not to fill name/student ID/personal information."],
            "Do not add identity information. If the template already contains identity text, ask whether to preserve or clear it.",
        )
    return field(
        "preserve_existing",
        0.72,
        ["No explicit identity-field instruction was found."],
        "Keep existing identity text and do not invent missing identity information.",
    )


def numbered_requirement_preview(text: str, limit: int = 12) -> list[str]:
    items: list[str] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        if re.match(r"^(（\d+）|\(\d+\)|\d+[.、]|[一二三四五六七八九十]+[、.])", line):
            items.append(line[:180])
        elif any(token in line for token in ("截图", "运行结果", "文字说明", "程序流程图", "实验现象", "Debug", "调试")):
            items.append(line[:180])
        if len(items) >= limit:
            break
    return items


def project_signal_preview(text: str) -> dict:
    patterns = {
        "course_or_title": r"(课程名称|实验名称|实验题目|实验项目|实验[一二三四五六七八九十0-9]).{0,80}",
        "platform_or_environment": r"(实验环境|实验平台|使用软件|开发环境|运行环境|DataGrip|MySQL|HCL|Keil|uVision|AIoT|IDEA|VS Code|Python|Java|Linux).{0,80}",
        "image_requirements": r"(.{0,30}(截图|运行结果|文字说明|程序流程图|实验现象|Debug|调试).{0,80})",
    }
    signals: dict[str, list[str]] = {}
    for key, pattern in patterns.items():
        hits = []
        for match in re.finditer(pattern, text, re.I):
            snippet = " ".join(match.group(0).split())
            if snippet and snippet not in hits:
                hits.append(snippet[:160])
            if len(hits) >= 8:
                break
        signals[key] = hits
    return signals


def build_semantic_packet(workspace: Path, context: dict, text: str, user_text: str, config_text: str) -> dict:
    analysis_path = workspace / "work" / "report_analysis.json"
    doc_structure_path = workspace / "work" / "doc_structure.json"
    analysis = read_json(analysis_path) if analysis_path.exists() else {}
    doc_structure = read_json(doc_structure_path) if doc_structure_path.exists() else {}
    blocks = doc_structure.get("blocks") or []
    tables = doc_structure.get("tables") or []
    return {
        "purpose": "Material packet for GPT/Codex semantic judgment. Scripts must not decide final experiment_type, document_pattern, or writing_mode.",
        "task_name": context.get("task_name"),
        "input_report": context.get("input_report"),
        "user_request": user_text,
        "task_yaml_constraints": {
            "image_mode": yaml_scalar(config_text, "image_mode"),
            "image_source_policy": yaml_scalar(config_text, "image_source_policy"),
            "identity_rules.fill_identity_fields": yaml_bool_under(config_text, "identity_rules", "fill_identity_fields"),
            "output_report_name": yaml_scalar(config_text, "output_report_name"),
        },
        "script_extracted_signals": project_signal_preview(text),
        "numbered_requirement_preview": numbered_requirement_preview(text),
        "doc_structure_summary": {
            "block_count": len(blocks),
            "table_count": len(tables),
            "paragraph_count": len(doc_structure.get("paragraphs") or []),
        },
        "legacy_report_analysis_for_reference_only": analysis,
        "required_gpt_output_fields": [
            "task_goal",
            "experiment_type",
            "document_pattern",
            "writing_mode",
            "coverage_mode",
            "detail_level",
            "image_mode",
            "identity_policy",
            "format_policy",
        ],
    }


def packet_markdown(packet: dict, directives: dict) -> str:
    signals = packet["script_extracted_signals"]
    reqs = packet["numbered_requirement_preview"]
    lines = [
        "# 第一阶段确认材料：任务理解",
        "",
        "脚本已经把 Word 模板拆解成结构化材料，但不会替你最终判断实验类型和报告填写类型。",
        "接下来应由 Codex/GPT 根据下面这些证据做语义判断，再把完整判断结果展示给用户确认。",
        "",
        "## 已知硬约束",
        "",
        f"- 任务名称：`{packet.get('task_name') or '未命名实验报告'}`",
        f"- 图片策略：`{directives['image_mode']['value']}`",
        f"- 身份字段：`{directives['identity_policy']['value']}`",
        f"- 确认模式：`{directives['confirmation_mode']['value']}`",
        "",
        "## Word 模板中提取到的线索",
        "",
    ]
    for title, key in (
        ("课程/实验标题线索", "course_or_title"),
        ("平台/环境/软件线索", "platform_or_environment"),
        ("截图/结果要求线索", "image_requirements"),
    ):
        lines.append(f"### {title}")
        hits = signals.get(key) or []
        if hits:
            lines.extend(f"- {hit}" for hit in hits)
        else:
            lines.append("- 未提取到明显线索，需要结合全文语义判断。")
        lines.append("")
    lines.extend(["## 编号任务/关键要求预览", ""])
    if reqs:
        lines.extend(f"- {item}" for item in reqs)
    else:
        lines.append("- 未提取到明显编号任务；仍需根据模板栏目判断写作方式。")
    lines.extend(
        [
            "",
            "## Codex/GPT 应输出给用户确认的内容",
            "",
            "请不要只说“识别为某某类型”。第一阶段确认必须至少包含：",
            "",
            "1. 实验类型：例如 `database_datagrip`、`network_hcl`、`java_idea`、`mcu_keil_aiot`、`c_data_structure`、`generic_report`，并说明依据。",
            "2. 报告填写/写作方式：例如 `fill_blanks`、`per_requirement`、`full_report`、`polish_only`、`image_replace_only`，并说明依据。",
            "3. 覆盖要求：`strict` / `normal` / `loose`，说明是否需要逐项覆盖编号任务。",
            "4. 图片策略：特别是用户要求 image-2 时必须显示 `gpt_image_2_only`。",
            "5. 身份字段策略：是否跳过姓名、学号、班级等字段。",
            "6. 发现的关键任务清单：用自然语言列出本报告要完成哪些项目。",
            "7. 需要用户确认或纠正的点。",
            "",
            "用户没有确认前，不得进入正文写入、图片生成或图片插入阶段。",
            "",
        ]
    )
    return "\n".join(lines)


def pending_directives(user_text: str, config_text: str) -> dict:
    return {
        "semantic_judgment_required": True,
        "task_goal": field(
            "complete_lab_report",
            0.8,
            ["Default formal task goal; final confirmation should be checked by Codex/GPT."],
            "Unless the user asks only for analysis/polish/image replacement, the task is treated as completing the report.",
        ),
        "experiment_type": field(
            PENDING,
            0.0,
            ["Scripts are not allowed to decide the final experiment type."],
            "Codex/GPT must judge this semantically from the decomposed Word content and user request.",
        ),
        "document_pattern": field(
            PENDING,
            0.0,
            ["Scripts only provide document-structure evidence."],
            "Codex/GPT must decide whether the report is blank-fill, per-requirement, full-report, polish-only, etc.",
        ),
        "writing_mode": field(
            PENDING,
            0.0,
            ["Scripts are not allowed to bind writing mode to experiment type."],
            "Codex/GPT must judge the report filling mode independently from the experiment domain.",
        ),
        "coverage_mode": field(
            PENDING,
            0.0,
            ["Coverage depends on template semantics and user intent."],
            "Codex/GPT must decide strict/normal/loose after reading the template requirements.",
        ),
        "detail_level": field(
            PENDING,
            0.0,
            ["Detail level depends on user intent and template requirements."],
            "Codex/GPT must decide brief/normal/complete/verbose.",
        ),
        "image_mode": likely_user_image_mode(user_text, config_text),
        "identity_policy": likely_identity_policy(user_text, config_text),
        "format_policy": field(
            "preserve_template",
            0.92,
            ["Formal Word reports should preserve the original template layout by default."],
            "Keep the Word table and paragraph layout unless the user allows minor adjustment.",
        ),
        "confirmation_mode": infer_confirmation_mode(user_text),
        "confirmed_by_user": False,
    }


def main() -> None:
    configure_utf8_stdio()
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    user_text_path = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "work" / "user_request.txt"
    context = read_json(workspace / "work" / "current_task_context.json")
    input_report = Path(context["input_report"])
    text = doc_text(input_report)
    user_text = read_text_if_exists(user_text_path)
    config_text = task_yaml_text(workspace)

    directives = pending_directives(user_text, config_text)
    packet = build_semantic_packet(workspace, context, text, user_text, config_text)
    write_json(workspace / "work" / "semantic_task_judgment_packet.json", packet)
    write_text(workspace / "work" / "semantic_task_judgment_packet.md", packet_markdown(packet, directives))
    write_json(workspace / "work" / "auto_task_directives.json", directives)
    write_text(workspace / "work" / "task_understanding_confirmation.md", render_task_confirmation(workspace))
    print("ACTION_REQUIRED_GPT_SEMANTIC_TASK_JUDGMENT")


if __name__ == "__main__":
    main()
