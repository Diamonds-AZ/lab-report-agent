# Cleanup Policy

## Keep in Project Workspace

Keep reusable project state:

- `input/`
- `assets/references/`
- `configs/`
- `work/report_analysis.md`
- `work/fill_plan.md`
- `work/doc_structure.json`
- `work/draft_text_fill_candidates.json`
- `work/refined_text_fill_plan.json`
- `work/draft_image_slot_candidates.json`
- `work/refined_image_plan.json`
- `work/report_text.md`
- `work/reference_analysis.md`
- `work/image_prompts.md`
- `work/image_list.md`
- `work/blank_fill_audit.md`
- `work/batch_check_report.md`

For a clean smoke test, clear run-specific state before starting unless the user asks to keep it:

- `work/`
- `output/reports/`
- `output/checks/`
- `output/images/`

## Do Not Leave by Default

Avoid leaving process code in the project workspace:

- Temporary copies of skill scripts.
- `__pycache__/`
- Throwaway conversion folders.
- Temporary image drafts not referenced by `image_list.md`.
- Debug-only JSON files.
- Hung Office conversion leftovers.
- `assets/generated_images/` legacy image pools; keep only if the user explicitly wants an archive, and never use it as an insertion source.

If a cleanup helper is added, it should support dry-run or log every path it deletes. It must never delete `assets/references/`, `configs/`, or `input/` by default.

## Skill Scripts

Keep deterministic process scripts inside the skill package. Run them from the skill directory or invoke them by absolute path. Copy scripts into the project workspace only when the user requests customization or debugging.

## Existing User Files

- Do not overwrite existing user files.
- If a default config is missing or empty, create it.
- If a config exists but appears outdated, write a migration note instead of rewriting it silently.

## Output Naming

- `first_run_test`: default to `output/reports/流程测试_实验报告.docx`.
- If an output file is open/locked, create a sibling file with a suffix such as `_更新流程` or `_run级修复`.
- `skill_production`: use `roster.yaml` `output_name`, or `学号_姓名_task_name.docx`.
