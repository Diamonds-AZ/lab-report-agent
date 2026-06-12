# Workflow

## Modes

- `first_run_test`: single test report, no real identity, no batch, no personal data in images or filenames.
- `skill_production`: future production mode. Batch identity filling is a later capability and requires explicit identity anchors before use.

## Required Order

### `pre_images`: semantic planning pause

1. Initialize missing workspace structure.
2. Create or resume `work/current_run.json`. When the same input and workflow stage are still active, the second `pre_images` pass must reuse the current run instead of creating a new run.
3. Resolve the input report.
4. Read `configs/task.yaml`; if `experiment_type=auto`, use `analyze_template.py` detection. If it is not `auto`, use the manual value.
5. Write `work/current_task_context.json`; `resolved_experiment_type` must never be `auto`.
6. Analyze template and write `work/report_analysis.md/json`.
7. Extract Word structure to `work/doc_structure.json`.
8. Extract broad text candidates to `work/draft_text_fill_candidates.json`.
9. Extract broad image slot candidates to `work/draft_image_slot_candidates.json`.
10. Stop with `ACTION_REQUIRED` until Codex/GPT writes:
    - `work/refined_text_fill_plan.json`
    - `work/refined_image_plan.json`

### `pre_images`: image generation pause

After refined plans exist:

1. Run `validate_plans.py semantic`.
2. Analyze reference images when present, writing `work/reference_analysis.md/json`.
3. Build prompts from `work/refined_image_plan.json`; do not build final image tasks from empty tables alone.
4. Prepare `work/image_generation_plan.json` and `work/runs/<run_id>/image_generation_plan.json`.
5. Stop with `ACTION_REQUIRED` for image generation.

Generated images must be copied to:

```text
work/runs/<run_id>/generated_images/
```

Use each item's `output_filename`.

### `post_images`

1. Validate `current_run.json`, `image_generation_plan.json`, and `generated_images_dir` have the same `run_id`.
2. Apply `work/refined_text_fill_plan.json` if text fill is enabled.
3. Insert images from the current run directory.
4. Table-cell image slots are supported through `target_table_index`.
5. Non-table `paragraph_blank_region` image slots are supported through `target_anchor` and `target_block_range`; the image is placed into the blank paragraph region and later blank paragraphs in the range are compressed.
6. Other non-table image slots must be written to unresolved image audit entries until their specific `layout_type` insertion is implemented.
7. Run hard-fail audit.

## Output Files

- `work/current_run.json`
- `work/current_task_context.json`
- `work/report_analysis.md`
- `work/report_analysis.json`
- `work/doc_structure.json`
- `work/draft_text_fill_candidates.json`
- `work/refined_text_fill_plan.json`
- `work/draft_image_slot_candidates.json`
- `work/refined_image_plan.json`
- `work/reference_analysis.md`
- `work/reference_analysis.json`
- `work/image_prompts.md`
- `work/image_generation_plan.json`
- `work/image_list.md`
- `work/text_fill_audit.md`
- `work/blank_fill_audit.md`
- `work/batch_check_report.md`
- `work/batch_check_report.json`
- `work/encoding_report.md`

## Image Rules

- `expected_image_count` is dynamic and comes from required items in `refined_image_plan.json`.
- Do not assume 4 images or 30 images.
- `assets/generated_images/` is legacy/archive only and must not be used as an insertion source.
- Missing current-run images fail immediately.
- Automatic image checking is off by default; the user reviews images and requests regeneration.
- Supported insertion layouts:
  - `table_cell` via `target_table_index`.
  - `paragraph_blank_region` via `target_anchor` and `target_block_range`.
- Currently reserved non-table layouts include complex `after_anchor`, arbitrary block-range merge, and rich replace-empty-paragraph behaviors.

## Text Fill Rules

Currently supported execution strategies:

- `replace_placeholder`
- `replace_blank_spaces`
- `fill_after_prefix`
- `fill_table_cell`

Currently unsupported or not stable:

- `insert_after_anchor`
- `replace_paragraph_content`
- `merge_following_explanation`

Unsupported strategies or unmatched in-place blanks must be recorded as unresolved and must not be appended to the paragraph.

## Identity Rules

- If `identity_rules.fill_identity_fields=false`, do not use roster identities in report fields, screenshots, filenames, hostnames, usernames, database names, project names, or paths.
- Batch identity filling is a later capability and requires explicit identity field anchors or a field map before enabling.
