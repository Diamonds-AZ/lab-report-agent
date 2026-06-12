# Semantic Text Fill Detection

## Principle

Use GPT/semantic reasoning to plan text fills, but let scripts edit Word. GPT must not directly modify `.docx`.

## Structure Extraction

Create `work/doc_structure.json`. Each candidate block should include:

- `block_id`
- `block_type`: `paragraph` or `table_cell`
- `text`
- `previous_text`
- `next_text`
- `section_path`
- `table_index`, `row_index`, `cell_index`
- `run_info`
- `has_many_spaces`
- `has_underscore`
- `has_placeholder`
- `is_empty`
- `is_command_prompt`
- `is_in_experiment_steps`
- `candidate_reason_by_script`

## Draft Candidates

Create `work/draft_text_fill_candidates.json`. Each item should include:

- `item_id`
- `block_id`
- `is_blank`
- `blank_type`: `command`, `result`, `reason`, `parameter_meaning`, `ip_address`, `port`, `view_name`, `image_placeholder`, `other`
- `original_text`
- `target_text`
- `answer`
- `replacement_strategy`: `replace_placeholder`, `fill_after_prefix`, `replace_blank_spaces`, `fill_table_cell`, `merge_following_explanation`, `skip`
- `confidence`: `high`, `medium`, `low`
- `reason`
- `need_user_review`

## Refined Plan

Codex/GPT semantic review must write `work/refined_text_fill_plan.json` from `work/doc_structure.json` and `work/draft_text_fill_candidates.json`.

- Do not copy or rename draft candidates into the refined plan.
- `apply_text_fill_plan.py` must read only `refined_text_fill_plan.json`.
- If the refined plan is missing, pause with `ACTION_REQUIRED`.
- If an item cannot find an in-place target, record it as unresolved and continue with the remaining items.

## Semantic Rules

Treat these as likely blanks:

- “其结果为        ”
- “其结果是        ”
- “产生这种结果的原因是        ”
- “通过        命令查看”
- “公网地址分别为        和        ”
- “端口号为        ”
- “在        视图下”
- “参数 xxx 的含义是        ”
- “请在下面的空格中填写”
- Command prompts missing commands, such as `[RTA] interface        `

Do not treat these as ordinary text blanks:

- Section titles.
- Captions.
- Already inserted image positions.
- Notes/instructions.
- Narrative paragraphs that do not ask for input.

## Run-Level Fill Rules

- Do not rewrite the whole paragraph.
- Replace only target blank runs or placeholder runs.
- Preserve question text run formatting.
- Keep underline on inserted answer runs when replacing an underlined blank.
- For multi-blank paragraphs, fill blanks in order.
- If a blank has no answer, leave it untouched and report it.
- Do not write `填写：`, `应填入：`, or `答案：` for fill-in blanks.

## Confidence

- `high`: auto-fill.
- `medium`: auto-fill and list in `blank_fill_audit.md`.
- `low`: do not auto-fill; list as suspected blank.

## Audit

`work/blank_fill_audit.md` must report:

- Number of semantic blank items.
- Number of auto-filled blocks.
- Skipped items.
- Low-confidence items.
- Remaining obvious blank placeholders.
- Remaining underlined blank runs.
- Forbidden prefixes.
- Items requiring user review.
