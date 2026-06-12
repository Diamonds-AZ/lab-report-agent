# Lab Report Agent

English | [简体中文](#lab-report-agent-中文)

`lab-report-agent` is a Codex skill for completing Chinese university lab-report templates from Word documents. It preserves the original Word structure, uses semantic planning for text fills and screenshot slots, and enforces audit gates for image provenance, encoding safety, unresolved blanks, and confirmation state.

This project is designed for report-generation workflows where structure matters: identity fields, in-place blanks, screenshot tables, image-source provenance, and final audit records are treated as first-class constraints.

## Features

- Copies a source Word template into an isolated workspace before editing.
- Converts legacy `.doc` inputs to `.docx` when LibreOffice is available.
- Extracts document structure from Word templates.
- Requires semantic confirmation before filling text or inserting screenshots.
- Builds refined text-fill and image-insertion plans.
- Supports `gpt_image_2_only` image provenance checks.
- Inserts screenshots into table cells or supported paragraph blank regions.
- Audits final reports for missing images, legacy-image use, encoding pollution, unresolved blanks, requirement coverage, and confirmation validity.

## Repository Contents

- `SKILL.md` - skill instructions and workflow contract.
- `scripts/` - execution, extraction, planning validation, insertion, and audit helpers.
- `docs/` - operating policies and known limitations.
- `prompts/` - reusable formal task prompt.
- `assets/default_configs/` - sanitized default workspace configuration.
- `schemas/` - JSON schemas for refined plans.
- `tests/smoke/` - small regression fixtures and metadata checks.

## What Is Not Included

This repository intentionally does not include real student reports, real course templates, generated reports, generated screenshots, `work/` directories, rosters with personal data, API keys, or institution-owned materials.

Do not publish user-provided `.doc/.docx` templates unless you have permission to redistribute them.

## Requirements

- Python 3.11 or newer.
- `python-docx`.
- `Pillow`.
- LibreOffice / `soffice` for automatic legacy `.doc` to `.docx` conversion.
- A Codex environment that can call the image generation tool when `gpt_image_2_only` is required.

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Quick Smoke Check

From the repository root:

```powershell
python tests\smoke\run_smoke_asset_checks.py
```

The smoke check verifies fixture metadata and confirmation/image-plan invariants. It does not call image-2 and does not generate a formal report.

## Typical Workflow

1. Prepare a fresh workspace with `scripts/prepare_new_task.py`.
2. Run `scripts/run_lab_report_task.py <workspace> pre_images`.
3. Confirm task understanding.
4. Create `work/refined_text_fill_plan.json` and `work/refined_image_plan.json`.
5. Confirm image insertion plan.
6. Generate required images and write the generated-image manifest.
7. Run `scripts/run_lab_report_task.py <workspace> post_images`.
8. Inspect `work/batch_check_report.md`, `work/blank_fill_audit.md`, and `work/encoding_report.md`.

See `SKILL.md` and `docs/current_operating_policy.md` for the full contract.

## Privacy And Safety

Before using this skill with real templates, keep all private inputs and outputs outside version control:

- `input/`
- `output/`
- `work/`
- `assets/generated_images/`
- rosters and identity-bearing configs
- generated `.doc/.docx` reports

The audit checks help catch common workflow mistakes, but human review is still required before submitting or publishing generated reports.

## License

MIT. See `LICENSE`.

---

# Lab Report Agent 中文

[English](#lab-report-agent) | 简体中文

`lab-report-agent` 是一个用于完成中文高校实验报告模板的 Codex skill。它面向 Word 实验报告场景，尽量保留原始模板结构，通过语义规划决定文字填充和截图插入位置，并用审计流程检查图片来源、编码安全、未填空白和确认状态。

这个项目适合处理结构要求比较强的实验报告：姓名学号栏、原位填空、截图表格、图片来源证明、最终审计记录，都会被当作正式约束处理。

## 功能

- 在编辑前把 Word 模板复制到隔离工作区，避免修改原文件。
- 在可用 LibreOffice / `soffice` 时，将旧版 `.doc` 转换为 `.docx`。
- 从 Word 模板中抽取段落、表格、空白和截图位等结构信息。
- 在写入正文或插入截图前，要求进行语义确认。
- 生成精炼的文字填充计划和图片插入计划。
- 支持 `gpt_image_2_only` 图片来源校验。
- 支持把截图插入表格单元格或已支持的段落空白区域。
- 审计最终报告中的缺失图片、旧图混用、编码污染、未解决空白、需求覆盖和确认状态。

## 仓库内容

- `SKILL.md` - skill 使用说明和流程契约。
- `scripts/` - 模板解析、计划校验、写入、插图和审计脚本。
- `docs/` - 当前运行策略、编码策略、最终检查和已知限制。
- `prompts/` - 正式实验报告任务提示词模板。
- `assets/default_configs/` - 脱敏后的默认工作区配置。
- `schemas/` - 精炼计划相关 JSON schema。
- `tests/smoke/` - 小型回归测试夹具和元数据检查。

## 不包含什么

这个仓库刻意不包含真实学生报告、真实课程模板、生成后的报告、生成截图、`work/` 运行目录、带个人信息的 roster、API key 或学校/机构材料。

除非你有再分发授权，不要把用户提供的 `.doc/.docx` 模板发布到公开仓库。

## 环境要求

- Python 3.11 或更高版本。
- `python-docx`。
- `Pillow`。
- LibreOffice / `soffice`，用于自动把旧版 `.doc` 转换为 `.docx`。
- 当任务要求 `gpt_image_2_only` 时，需要能调用图片生成工具的 Codex 环境。

安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

## 快速烟测

在仓库根目录运行：

```powershell
python tests\smoke\run_smoke_asset_checks.py
```

这个烟测只检查测试夹具和确认/图片计划相关约束，不会调用 image-2，也不会生成正式实验报告。

## 典型流程

1. 使用 `scripts/prepare_new_task.py` 初始化一个干净工作区。
2. 运行 `scripts/run_lab_report_task.py <workspace> pre_images`。
3. 确认第一阶段任务理解。
4. 创建 `work/refined_text_fill_plan.json` 和 `work/refined_image_plan.json`。
5. 确认第二阶段图片插入计划。
6. 生成所需图片，并写入图片来源 manifest。
7. 运行 `scripts/run_lab_report_task.py <workspace> post_images`。
8. 检查 `work/batch_check_report.md`、`work/blank_fill_audit.md` 和 `work/encoding_report.md`。

完整流程契约见 `SKILL.md` 和 `docs/current_operating_policy.md`。

## 隐私与安全

处理真实模板时，请确保以下内容不进入版本控制：

- `input/`
- `output/`
- `work/`
- `assets/generated_images/`
- roster 和任何带身份信息的配置
- 生成后的 `.doc/.docx` 报告

审计流程能帮助发现常见问题，但提交、发布或上交生成报告前，仍然需要人工快速复核。

## 许可证

MIT。详见 `LICENSE`。
