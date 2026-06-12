# Current Operating Policy

This document records the current stable operating policy for formal lab-report tasks. It is intended to preserve the workflow behavior across new conversations.

## Before Starting A Formal Task

- Clean task residue before a new formal task:
  - Clear `work/`.
  - Clear `output/reports/`.
  - Clear generated images unrelated to the current task.
  - Preserve reference assets under `assets/references/`, including HCL, DataGrip, IDEA, and VS Code references.
- Do not modify the original report template.
- Copy the source template into the workspace `input/` directory, then operate only on that copy.
- Write completed reports to `output/reports/`.
- Formal report filenames default to `<task_name>-完成版.docx`.
- If `configs/task.yaml` explicitly sets `output_report_name`, use that filename instead after sanitizing unsafe Windows filename characters.
- After extracting `work/doc_structure.json`, require first-stage task-understanding confirmation before semantic planning continues.
- The first-stage recognition step is semantic, not script-driven. Scripts may summarize Word structure and collect evidence, but they must not finalize `experiment_type`, `document_pattern`, `writing_mode`, `coverage_mode`, or `detail_level` with keyword rules.
- The same rule applies to report filling and image insertion. After Word decomposition, scripts may only provide document-structure facts. They must not decide final text-fill slots or image slots from keyword hints such as `下图`, `如下图`, `截图`, `结果为`, or blank paragraphs.
- `scripts/infer_task_directives.py` must produce `work/semantic_task_judgment_packet.md/json` and a pending `work/auto_task_directives.json`. Codex/GPT must read the packet, make the actual semantic judgment, replace the pending values, then run `scripts/render_task_confirmation.py <workspace>`.
- The first-stage confirmation shown to the user must be the fixed page in `work/task_understanding_confirmation.md`. It must not be replaced by a one-sentence summary. The page must include:
  - what task will be done;
  - experiment type and evidence;
  - Word template pattern;
  - report filling/writing mode and evidence;
  - coverage mode and detail level;
  - image policy, especially `gpt_image_2_only` when requested;
  - identity policy;
  - format policy;
  - key template requirements that will be covered;
  - uncertain points requiring correction;
  - plain-language examples of how the user can confirm or request changes.
- Confirmation Markdown files are audit records, not substitutes for the chat message. If `work/action_required.json` has `must_display_inline_to_user=true`, Codex must read its `display_file` and show the relevant confirmation content directly in the conversation. Sending only a path, attachment, or short summary is a workflow bug.
- If the user says the understanding is wrong or asks for changes, treat it as a revision request, not a failure. Record the feedback with `scripts/handle_user_feedback.py <workspace> record --stage task_understanding --feedback-file <utf8_text_file>`, revise `work/auto_task_directives.json`, regenerate `work/task_understanding_confirmation.md`, and ask again.
- Store confirmed task understanding in `work/task_directives.json` with `confirmed_by_user=true`.
- Confirmation is manual by default. If the user did not explicitly allow full automation, Codex must stop and ask the user before running `confirm_task_directives.py` or `confirm_image_plan.py`.
- A valid manual confirmation must record `confirmation_source=explicit_user_reply` or `confirmation_source=user_reply`.
- Agent auto-confirmation is valid only when the user explicitly allowed it and the file records `confirmation_mode=agent_auto_allowed` plus `confirmation_source=agent_auto_allowed_by_user`.
- Agent auto-confirmation must also record `auto_confirmation_grant_text`, containing the user's explicit full-automation request. Without this grant text, the confirmation is invalid.
- Hand-editing `confirmed_by_user=true` without a valid confirmation source is not a valid confirmation and must be treated as unconfirmed.
- Do not bind `experiment_type` to `writing_mode`. Experiment type describes the domain/platform; document pattern describes the Word template structure; writing mode describes how this report should be completed.
- If no preset profile matches, generate `work/discovered_profile_draft.yaml` and ask the user whether to use it once or save it as `configs/profiles/discovered/<slug>.yaml`.

## Identity Fields

- By default, do not fill class, student ID, student name, or identity-derived fields.
- Identity handling must use one explicit policy:
  - `preserve_existing_identity`: keep identity text already present in the template, but do not add new identity text.
  - `clear_identity_fields`: remove existing identity text when the user requests no identity information in the final report.
  - `fill_identity_fields`: fill identity fields from an approved roster or user-provided values.
- Fill identity fields only when the user explicitly requests it, or when a validated batch production workflow is enabled.
- Future identity filling must use explicit anchors, roster configuration, or a field map.
- Do not use broad full-document replacement for identity fields.
- Do not place identity data in screenshots, filenames, hostnames, database names, usernames, project names, or paths unless explicitly requested.

## Image Planning

- Image count is dynamic and comes from `work/refined_image_plan.json`.
- GPT/Codex semantic planning must classify every required image target with `zone_type`.
- Allowed `zone_type` values are `answer_area`, `question_area`, `reference_material`, `identity_area`, and `unknown`.
- Formal image insertion should target `answer_area`. `question_area` and `reference_material` are forbidden unless the user explicitly asks to modify question/reference material and the item records `explicitly_allowed_question_area_image=true`.
- Long task requirement text can contain phrases such as `下图` or `如下图`; these phrases alone are not evidence that an answer image belongs there.
- If the template has an explicit divider such as `实验报告模板`, `程序流程图`, `实验现象`, or `实验结果展示`, prefer the answer area after that divider over earlier question/reference explanation.
- After `work/refined_image_plan.json` is available, require second-stage image insertion confirmation before image generation or insertion continues.
- The second-stage confirmation shown to the user must be the fixed table in `work/image_insertion_confirmation.md`. It must list image number, zone type, insertion position in plain language, nearby anchor text, covered requirement IDs and original requirement text when available, image content, required visible code/result/error content, source policy, mandatory image-2 flag, warnings, and plain-language examples of how the user can request changes.
- `work/image_insertion_confirmation.md` must exist and contain that table before an image plan can be marked confirmed. A confirmed image plan without this file is an audit failure.
- Codex must paste the second-stage table into the conversation before asking the user to confirm or revise it. The saved Markdown is the durable record only.
- If the user asks to move, remove, add, merge, or change an image, record the feedback with `scripts/handle_user_feedback.py <workspace> record --stage image_plan --feedback-file <utf8_text_file>`, revise `work/refined_image_plan.json`, regenerate `work/image_insertion_confirmation.md`, and ask again.
- Store image-plan confirmation in `work/refined_image_plan.json` with `confirmed_by_user=true` and a valid `confirmation_source`.
- Do not assume a fixed number such as 4 or 30 images.
- Do not merge images merely to reduce count.
- Merge only when GPT/Codex semantic planning determines that a combined screenshot is faithful to the template slot.
- Each required image should map to its intended slot, especially for repeated screenshot tables.
- Images may only be inserted from the current run directory:

```text
work/runs/<run_id>/generated_images/
```

- Do not use legacy images or historical run images.
- `image_generation_plan.json` items should include `image_source`; audit reports summarize these values in `image_source_summary`.
- Do not call generated or synthetic images real screenshots unless `image_source=real_screenshot`.
- If the user requires image-2, use `image_mode=gpt_image_2_only` / `image_source_policy=gpt_image_2_only`. In that mode, final images must be listed in `work/generated_images_manifest.json` and validate as `declared_source=gpt_image_2`, `created_by=image_2`, `generation_mode=gpt_image_2_only`, with matching `sha256`.
- In `gpt_image_2_only` mode, do not silently substitute script-rendered, dummy, placeholder, synthetic, legacy, or older-run images.
- When `ACTION_REQUIRED_GENERATE_IMAGE_2_IMAGES` is emitted, Codex must call `image_gen` for every item in `work/image_generation_plan.json`. Save every generated PNG to the current run `generated_images_dir` with the exact `output_filename`, then run `build_generated_images_manifest.py <workspace> gpt_image_2 image_2` and `validate_generated_images_manifest.py <workspace>`.
- `work/image_2_generation_todo.md` is the human/agent task sheet for mandatory image-2 generation. Follow it before `post_images`.
- `assets/generated_images/` is legacy/archive only and must never be an insertion source.
- Automatic image checking is off by default.
- The user manually reviews generated images and requests regeneration when needed.
- Image quality audit is warning-only by default.
- Do not automatically call image-2 or regenerate images based only on warning-level quality checks.

## High Image Count

- If `expected_image_count` exceeds `image_rules.image_count_policy.confirm_threshold`, stop with `ACTION_REQUIRED`.
- After user approval, write `work/image_count_confirmation.json`.
- The confirmation must match the current `run_id`, `expected_image_count`, `confirm_threshold`, `generated_images_dir`, and plan fingerprint.
- Both `pre_images` and `post_images` must respect the confirmation state.
- Do not bypass high-count confirmation by temporarily raising `confirm_threshold`.

## Image Insertion

- `table_cell` insertion must clear or relax fixed row height where possible so screenshots are not cropped.
- `paragraph_blank_region` has a minimum supported insertion path through `target_anchor` and `target_block_range`.
- Unsupported or complex `layout_type` values must be recorded as unresolved.
- Do not insert unsupported image layouts randomly or into the nearest convenient location.

## Text Filling

- Text filling must go through `work/refined_text_fill_plan.json`.
- GPT/Codex semantic planning must classify every text-fill item with `zone_type`.
- Formal text filling should target `answer_area`, explicit blanks, or user-approved replacement targets. `question_area` and `reference_material` must not be rewritten unless the user explicitly asks to edit them and the item records `explicitly_allowed_question_area_edit=true`.
- If the user asks to change wording, tone, length, code detail, result text, or summary, record the feedback with `scripts/handle_user_feedback.py <workspace> record --stage text_plan --feedback-file <utf8_text_file>`, revise `work/refined_text_fill_plan.json`, regenerate the relevant preview/confirmation, and ask again.

## Revision Feedback Protocol

User-facing choices are:

- confirm and continue;
- request changes in natural language;
- cancel/stop the task.

Codex must not require the user to edit JSON. When the user requests changes:

1. Save the user's feedback to a UTF-8 text file.
2. Run `scripts/handle_user_feedback.py <workspace> record --stage auto --feedback-file <file>`.
3. Revise the relevant semantic artifact:
   - `work/auto_task_directives.json` for task understanding;
   - `work/refined_text_fill_plan.json` for text;
   - `work/refined_image_plan.json` for image location/content/count;
   - image prompts or manifest only for generation-quality feedback.
4. Regenerate the relevant fixed confirmation Markdown:
   - task understanding: run `scripts/render_task_confirmation.py <workspace>`;
   - image plan: run `scripts/build_image_insertion_confirmation.py <workspace>`.
5. Show the revised confirmation to the user.
6. After the user approves the revision, run `scripts/handle_user_feedback.py <workspace> resolve --notes "..."`

`run_lab_report_task.py` must stop while `work/latest_user_feedback.json` has `status=pending_revision`.
- If `writing_mode=per_requirement`, extract `work/requirement_items.json` and ensure text/image plans cover required items or explicitly record skipped items.
- Do not copy or rename draft candidates into the refined plan.
- Do not append answers to the end of the paragraph or document when the original blank cannot be found.
- Do not write answers with prefixes such as `应填入：`, `答案：`, `原因：`, or `说明：`.
- For prompts such as `请补充完整命令`, prefer filling the command text in place.
- Screenshots should support command evidence, not replace required in-place text answers.

## Audit

After `post_images`, always inspect:

- `work/batch_check_report.md`
- `work/batch_check_report.json`
- `work/blank_fill_audit.md`
- `work/encoding_report.md`

Required checks:

- `hard_fail`
- `expected_images`, `generated_images`, and `inserted_images`
- `legacy_image_used`
- `encoding_pollution`
- `unresolved_text`
- `expected_blank_count`, `intentionally_unchanged_count`, and `real_unresolved_text_count`
- `image_source_summary`
- `unresolved_image`
- `unresolved_image_insert`
- `suspected_cropped`
- `quality_warnings`

If the audit reports a hard fail, do not deliver the report as complete.
Identity blanks requested by the user should count as expected blanks, not hard failures. Real unresolved body text should remain a hard failure or strong action item.
