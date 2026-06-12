# Formal Lab Report Generation Prompt

Use this prompt template in a new conversation when the user wants a formal lab report generated with `lab-report-agent`.

## Prompt Template

Use the `lab-report-agent` skill to complete the specified Word lab-report template.

Requirements:

- This turn generates the report only; do not repair or redesign the skill unless the user explicitly asks.
- Before starting, clean the workspace task residue:
  - `work/`,
  - `output/reports/`,
  - generated images unrelated to the current run.
- Preserve all reference images under `assets/references/`.
- Do not modify the original template.
- Copy the source template into workspace `input/`.
- Read `configs/task.yaml` and resolve `experiment_type`.
- If `experiment_type=auto`, use template analysis to determine the final experiment type.
- The final `resolved_experiment_type` must not be `auto`.
- Run the first `pre_images` pass to generate:
  - `work/doc_structure.json`,
  - `work/draft_text_fill_candidates.json`,
  - `work/draft_image_slot_candidates.json`.
- GPT/Codex must semantically create:
  - `work/refined_text_fill_plan.json`,
  - `work/refined_image_plan.json`.
- Do not copy or rename draft candidates as refined plans.
- Image count must come dynamically from `refined_image_plan.json`.
- Do not assume 4 images, 30 images, or any fixed count.
- Do not merge screenshots merely to reduce count.
- If `expected_image_count` exceeds `confirm_threshold`, stop and ask the user for confirmation.
- After confirmation, write `work/image_count_confirmation.json`.
- Run the second `pre_images` pass to generate `work/image_generation_plan.json`.
- When screenshots are needed, call image-2 or the available image generation tool according to the current environment.
- Copy each generated image into the current run directory:

```text
work/runs/<run_id>/generated_images/
```

- Rename each image exactly to its `output_filename` from `image_generation_plan.json`.
- Do not use:
  - `assets/generated_images/`,
  - `output/images/`,
  - `.codex/generated_images/`,
  - older `work/runs/<old_run_id>/generated_images/`.
- Run `post_images` to apply text fills, insert images, and audit.
- Inspect:
  - `work/batch_check_report.md`,
  - `work/blank_fill_audit.md`,
  - `work/encoding_report.md`.
- Deliver the output report path and audit summary.

Default identity policy:

- Do not fill class, student ID, or name unless the user explicitly requests it.
- Do not put personal identity in screenshots, filenames, paths, hostnames, database names, project names, or watermarks unless explicitly requested.

Final delivery summary should include:

- output report path,
- `hard_fail`,
- expected/generated/inserted image counts,
- `legacy_image_used`,
- `encoding_pollution`,
- unresolved text/image counts,
- any remaining manual review notes.
