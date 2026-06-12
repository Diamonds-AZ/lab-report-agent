# 02 GPT Image-2 Only No Script Fallback

Purpose: verify that `gpt_image_2_only` cannot be satisfied by script images, dummy images, placeholders, synthetic renderers, old run images, or manual substitutions.

Expected behavior:

- `generated_images_manifest.json` is required.
- Every manifest item must have:
  - `declared_source: gpt_image_2`
  - `created_by: image_2`
  - `generation_mode: gpt_image_2_only`
  - valid SHA-256 matching the current run file.
- Validation must fail if a dummy/script/synthetic source appears.
