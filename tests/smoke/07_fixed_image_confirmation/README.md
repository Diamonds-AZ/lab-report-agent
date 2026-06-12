# Smoke 07: Fixed Second-Stage Image Confirmation

Purpose: ensure the second-stage image confirmation always uses a stable, readable table.

Expected behavior:

- The user-facing file is `work/image_insertion_confirmation.md`.
- The table explains where each image goes, what it covers, and what must appear inside the image.
- The table states whether image-2 is mandatory.
- The user can confirm or request changes such as moving, adding, removing, or changing images.
- `confirm_image_plan.py` must reject confirmation if this table is missing or incomplete.

