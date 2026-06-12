# 01 Confirmation Required

Purpose: verify that a new formal task stops at first-stage task understanding until the user explicitly confirms.

Expected behavior:

- `infer_task_directives.py` produces `semantic_task_judgment_packet.md/json`.
- `auto_task_directives.json` remains pending until GPT/Codex writes real semantic values.
- `confirm_task_directives.py` rejects pending directives.
- No final report should be generated before confirmation.
