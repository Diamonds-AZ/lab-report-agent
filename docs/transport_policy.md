# Transport Policy

## Purpose

This skill handles Chinese report text, fill answers, and image prompts. Large or non-ASCII content must move through UTF-8 files, not command-line arguments, shell pipes, or heredocs.

## Rules

- Command-line arguments may contain only paths, stage names, run IDs, and config paths.
- Do not pass Chinese report body text, fill answers, Markdown sections, or image prompts through shell pipes.
- Do not pass Chinese paths, complex JSON, or large Chinese strings through PowerShell here-strings, PowerShell pipes, `python -c`, or temporary inline Python scripts.
- Pipes and stdout are for short control messages only, such as `ACTION_REQUIRED`.
- Generated plans must be stored under `work/` or `work/runs/<run_id>/`.
- Image generation outputs must be copied into `work/runs/<run_id>/generated_images/` as specified by `work/image_generation_plan.json`.
- `assets/generated_images/` is legacy/archive only and must not be used as an insertion source.
- `post_images` must not read `assets/generated_images/`, `output/images/`, `.codex/generated_images/`, or older `work/runs/<old_run_id>/generated_images/` directories.

## Required Planning Files

- `work/current_run.json`
- `work/current_task_context.json`
- `work/doc_structure.json`
- `work/draft_text_fill_candidates.json`
- `work/refined_text_fill_plan.json`
- `work/draft_image_slot_candidates.json`
- `work/refined_image_plan.json`
- `work/image_prompts.md`
- `work/image_generation_plan.json`
- `work/runs/<run_id>/generated_images/`

## Failure Behavior

Scripts must fail or pause rather than repair silently when:

- `refined_text_fill_plan.json` is missing and text fill is enabled.
- `refined_image_plan.json` is missing and image generation/insertion is enabled.
- Run IDs do not match.
- Generated images are missing from the current run directory.
- Generated image filenames do not match `output_filename`.
- Output introduces new `???` or replacement characters.
- A non-table image slot is encountered before anchor/range insertion is implemented; record it as unresolved instead of inserting randomly.
