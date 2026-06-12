# Lab Report Agent Smoke Tests

These smoke tests are small regression assets for the skill workflow. They are not formal lab reports.

Use them after changing planning, confirmation, image-source, or insertion logic.

Current focus:

- New conversations must not skip confirmation gates.
- First-stage confirmation must use the fixed user-facing template.
- Second-stage image confirmation must use the fixed table template.
- GPT/Codex, not scripts, must decide semantic report zones.
- Image plans must declare `zone_type`.
- Images must not be inserted into question/reference areas unless explicitly allowed.
- `gpt_image_2_only` must not be satisfied by dummy, synthetic, or script-rendered images.

Run the lightweight asset check:

```powershell
python tests\smoke\run_smoke_asset_checks.py
```

The asset check verifies the smoke fixtures and expected metadata. It does not generate a formal report and does not call image-2.
