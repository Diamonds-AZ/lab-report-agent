# 04 Zone Type Required

Purpose: verify that refined text and image plans cannot proceed without `zone_type`.

Expected behavior:

- `validate_plans.py semantic` fails if required text/image items lack `zone_type`.
- `build_image_prompts.py` fails if required image items lack `zone_type`.
- `prepare_image_generation.py` carries `zone_type` forward into `image_generation_plan.json`.
- `insert_report_images.py` rejects missing `zone_type`.
