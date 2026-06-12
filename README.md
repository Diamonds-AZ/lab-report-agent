# Lab Report Agent

`lab-report-agent` is a Codex skill for completing Chinese university lab-report templates from Word documents. It preserves the original Word structure, uses semantic planning for text fills and screenshot slots, and enforces audit gates for image provenance, encoding safety, and unresolved blanks.

## What It Does

- Copies a source Word template into an isolated workspace before editing.
- Converts legacy `.doc` inputs to `.docx` when LibreOffice is available.
- Extracts document structure from Word templates.
- Requires semantic confirmation before filling text or inserting screenshots.
- Builds refined text-fill and image-insertion plans.
- Supports `gpt_image_2_only` image provenance checks.
- Inserts screenshots into table cells or supported paragraph blank regions.
- Audits final reports for missing images, legacy-image use, encoding pollution, unresolved blanks, and confirmation state.

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
