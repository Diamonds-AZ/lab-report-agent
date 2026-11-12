# Lab Report Agent

English | [简体中文](#lab-report-agent-中文)

`lab-report-agent` is a Codex skill for completing Chinese university lab-report templates from Word documents. It preserves the original Word structure, uses semantic planning for text fills and screenshot slots, and enforces audit gates for image provenance, encoding safety, unresolved blanks, and confirmation state.

## Install As A Codex Skill

In PowerShell, clone this repository into the Codex skills directory:

```powershell
git clone https://github.com/Diamonds-AZ/lab-report-agent.git "$HOME\.codex\skills\lab-report-agent"
```

Alternatively, download the repository ZIP and extract it so `SKILL.md` is at `<Codex skills directory>\lab-report-agent\SKILL.md`. Then start a new Codex conversation and invoke `$lab-report-agent`.

This project is designed for report-generation workflows where structure matters: identity fields, in-place blanks, screenshot tables, image-source provenance, and final audit records are treated as first-class constraints.

## Features

- Copies a source Word template into an isolated workspace before editing.
- Converts legacy `.doc` inputs to `.docx` with LibreOffice / `soffice`, WPS COM, or Microsoft Word COM on Windows.
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
- `docs/first_run_setup.md` - first-run environment checks and consent-based setup guidance.

## What Is Not Included

This repository intentionally does not include real student reports, real course templates, generated reports, generated screenshots, `work/` directories, rosters with personal data, API keys, or institution-owned materials.

Do not publish user-provided `.doc/.docx` templates unless you have permission to redistribute them.

## Compatibility And Beta Status

- This skill is currently designed and tested only for Codex. The author has not tested it with other vibe-coding tools.
- Image generation currently assumes the Codex `image_gen` / image-2 workflow. If you use another tool, you may need to adapt the image-generation plan, generated-image manifest, or connect your own external image model.
- This project is a test/beta skill, not a polished product. It may struggle with some lab-report types, unusual Word templates, or strict institution-specific formatting rules.
- We plan to keep iterating toward a real experiment-software execution interface, including app-specific adapters and real evidence capture. This is a roadmap commitment, not a capability in the current release; no release date is promised.
- Always inspect the generated report, screenshots, and audit files before submitting anything.

## What To Tell Codex When You Start

When invoking the skill, describe the task as clearly as possible. Useful details include:

- Student identity to fill, such as name, student ID, and class, if the report should include them.
- Whether screenshots should be generated with image-2, provided manually, captured from real software, or produced by another source.
- Screenshot requirements, such as network-design experiments that need command-line screenshots only, no main software page, specific visible commands, device names, host names, database names, or output text.
- The experiment topic, software/platform, report type, and any parts of the template that must or must not be changed. If you do not describe the experiment type, the workflow will infer it.
- Whether to generate one report or multiple reports from a single template.

## Optional Configuration And Batch Use

- You can configure reference images, for example UI style references for HCL, DataGrip, or other software screenshots.
- The skill currently supports configuring multiple student names and IDs to generate multiple report copies in one run.
- Batch generation is a test capability. The author has not optimized it for large rosters, complex per-student customization, or production use.

## Requirements

- Python 3.11 or newer.
- `python-docx`.
- `Pillow`.
- `.docx` templates do not need an office suite for conversion.
- Legacy `.doc` conversion requires at least one converter. LibreOffice is the recommended cross-platform option; WPS Office or Microsoft Word are optional Windows COM fallbacks.
- A Codex environment that can call the image generation tool when `gpt_image_2_only` is required.

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

For a first run on an unfamiliar computer, let Codex check the environment against the actual template:

```powershell
python scripts\setup_environment.py --input "<template-path>" --json
```

If Python 3.11+ is available but dependencies are missing, an isolated environment can be prepared in the task workspace after the user approves it:

```powershell
python scripts\setup_environment.py --install-python-deps --venv "<workspace>\.venv"
```

The helper never installs software by default. It does not install Python, LibreOffice, experiment applications, or image-generation tools. See [`docs/first_run_setup.md`](docs/first_run_setup.md) for consent and recovery rules.

### Legacy `.doc` Conversion Setup

Install LibreOffice from the [official download page](https://www.libreoffice.org/download/download/). The converter checks `PATH`, the process environment variable `LAB_REPORT_SOFFICE_PATH`, and an optional skill-local `.env` file (ignored by Git) containing `LAB_REPORT_SOFFICE_PATH=<path to soffice.com or soffice.exe>`. If LibreOffice is not found on first use, the skill asks once for the executable path or installation folder; `scripts/convert_legacy_doc.py --configure-soffice <path>` validates and saves it for later tasks. The same configured executable is used for conversion and document rendering. On Linux or macOS, install LibreOffice using the operating system's package manager and make sure `soffice` is on `PATH`.

Check what this computer can attempt before processing a legacy template:

```powershell
python scripts\convert_legacy_doc.py --check
```

The check finds LibreOffice on `PATH` or at the saved skill-local path and reports whether the Windows COM fallback ProgIDs are registered. On Windows, this registration check reads `HKEY_CLASSES_ROOT\Kwps.Application` and `HKEY_CLASSES_ROOT\Word.Application`; it does not launch the applications. Actual COM activation is verified only when a conversion runs. The converter uses isolated LibreOffice profiles, points its subprocess at an adjacent bundled Python runtime when present, and validates the resulting DOCX package. It does not change global Python settings. If LibreOffice is not found on first use, the skill asks once for a custom executable path before choosing a COM fallback and stores the validated path for later tasks. If all local converters fail, provide a `.docx` template or install a supported converter. LibreOffice's [Windows installation guide](https://www.libreoffice.org/get-help/install-howto/windows/) and [command-line documentation](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html) describe installation and command-line use.

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

## 安装为 Codex Skill

在 PowerShell 中将仓库克隆到 Codex skills 目录：

```powershell
git clone https://github.com/Diamonds-AZ/lab-report-agent.git "$HOME\.codex\skills\lab-report-agent"
```

也可以下载仓库 ZIP，并解压到 `<Codex skills directory>\lab-report-agent\`，确保 `SKILL.md` 位于该目录根部。之后新建 Codex 对话并调用 `$lab-report-agent`。

这个项目适合处理结构要求比较强的实验报告：姓名学号栏、原位填空、截图表格、图片来源证明、最终审计记录，都会被当作正式约束处理。

## 功能

- 在编辑前把 Word 模板复制到隔离工作区，避免修改原文件。
- 使用 LibreOffice / `soffice` 将旧版 `.doc` 转换为 `.docx`；Windows 下也支持 WPS COM 和 Microsoft Word COM 自动化转换。
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

## 兼容性与测试版状态

- 这个 skill 目前仅针对 Codex 设计和测试。作者并未使用其他 vibe-coding 工具测试过。
- 生图流程目前默认使用 Codex 的 `image_gen` / image-2 工作流。如果你在其他工具里使用，可能需要自行调整图片生成计划、图片 manifest，或外接自己的生图模型。
- 这个项目仍是测试版 skill，不是成熟产品。面对某些实验报告类型、特殊 Word 模板或严格的学校格式要求时，可能会力不从心。
- 我们计划在后续版本中持续迭代，逐步接入真实实验软件的实操接口，包括按软件适配的执行方式和真实证据采集。这是后续路线图承诺，当前版本尚未实现，也不承诺具体发布日期。
- 提交前请务必人工检查生成后的报告、截图和审计文件。

## 开始调用时建议说明什么

调用 skill 时，尽量把任务描述清楚。建议说明：

- 需要填写的学生身份信息，例如姓名、学号、班级。
- 截图使用什么来源，例如 image-2 生成、手动提供、真实软件截图，或其他生图来源。
- 截图的具体要求，例如某些网络设计相关实验，只要命令行截图、不要软件主页面、必须出现哪些命令、设备名、主机名、数据库名或输出内容。
- 实验主题、使用的软件/平台、报告类型，以及模板中哪些内容必须修改或不能修改。（若不描述实验类型，工作流会自行推测）
- 是只生成一份报告，还是根据一个模板，一次性生成多份报告。

## 可选配置与批量能力

- 可以配置参考图，例如 HCL，DataGrip 或其他软件截图的界面风格参考。
- 目前支持配置多个人的姓名和学号，并在一次运行中生成多份报告。
- 批量生成仍是测试能力。作者尚未针对大名单、复杂的逐人定制或生产级使用做优化。

## 环境要求

- Python 3.11 或更高版本。
- `python-docx`。
- `Pillow`。
- `.docx` 模板不需要额外安装办公软件来做格式转换。
- 转换旧版 `.doc` 至少需要一个本地转换器。推荐跨平台使用 LibreOffice；Windows 下也可选用 WPS Office 或 Microsoft Word COM 作为回退。
- 当任务要求 `gpt_image_2_only` 时，需要能调用图片生成工具的 Codex 环境。

安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

首次在陌生电脑上使用时，可让 Codex 根据实际模板先检查环境：

```powershell
python scripts\setup_environment.py --input "<模板路径>" --json
```

如果 Python 3.11+ 已安装但缺少依赖，用户批准后，可以在本次任务工作区创建隔离环境：

```powershell
python scripts\setup_environment.py --install-python-deps --venv "<工作区>\.venv"
```

该工具默认只检查，不会自行安装软件；它不会安装 Python、LibreOffice、实验软件或生图工具。安装授权与失败后的处理方式见[`docs/first_run_setup.md`](docs/first_run_setup.md)。

### 旧版 `.doc` 转换环境

从 [LibreOffice 官方下载页](https://www.libreoffice.org/download/download/)安装 LibreOffice。转换器会检查 `PATH`、进程环境变量 `LAB_REPORT_SOFFICE_PATH`，以及 skill 本地 `.env` 文件（该文件已被 Git 忽略），其中保存 `LAB_REPORT_SOFFICE_PATH=<soffice.com 或 soffice.exe 的路径>`。首次检查未找到 LibreOffice 时，skill 应询问一次可执行文件路径或安装目录；用户提供后通过 `scripts/convert_legacy_doc.py --configure-soffice <路径>` 验证并保存，后续任务自动复用，同一程序也用于文档渲染。Linux 或 macOS 用户可通过系统包管理器安装 LibreOffice，并确保 `soffice` 在 `PATH` 中。

处理旧版模板前，可以先检查本机可尝试的转换路径：

```powershell
python scripts\convert_legacy_doc.py --check
```

该检查会从 `PATH` 或 skill 保存的路径定位 LibreOffice，并报告 Windows 回退转换器的 COM ProgID 是否已注册。Windows 下会检查注册表中的 `HKEY_CLASSES_ROOT\Kwps.Application` 和 `HKEY_CLASSES_ROOT\Word.Application`，但不会在预检时启动应用；WPS/Word 是否能真正启动，只有实际转换时才能确认。首次文档渲染前或转换 `.doc` 时若未找到 LibreOffice，skill 应询问一次用户是否提供可执行文件路径，再选择 WPS/Word 回退；用户给出后保存配置并在后续任务复用。转换器会使用隔离的 LibreOffice 配置目录；如果 `soffice` 同目录包含自带 Python 运行时，则仅为 LibreOffice 子进程设置对应的 `PYTHONHOME`，不会更改用户或系统的全局 Python 设置；生成后还会校验 DOCX 文件包。如果本机所有转换器都失败，请提供 `.docx` 模板，或安装受支持的转换器。LibreOffice 的[Windows 安装指南](https://www.libreoffice.org/get-help/install-howto/windows/)和[命令行文档](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)提供了安装与命令行使用说明。

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
