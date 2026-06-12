# Smoke 06: Fixed First-Stage Confirmation

Purpose: ensure the first-stage task-understanding confirmation is not a free-form one-sentence summary.

Expected behavior:

- The user-facing file is `work/task_understanding_confirmation.md`.
- It uses the fixed section order required by the skill.
- It explains the task in plain Chinese for non-technical users.
- It tells the user they can confirm or request changes in natural language.
- `confirm_task_directives.py` must reject confirmation if the fixed-format file is missing or incomplete.

