# Smoke Test Status

This document records the stage-gate results that currently define the stable workflow behavior.

## Passed Smoke And Formal Samples

### smoke01: Minimum Closed Loop

- Scope:
  - One text fill.
  - One table screenshot slot.
- Verified:
  - `draft_text_fill_candidates.json` and `draft_image_slot_candidates.json` are refined by GPT/Codex.
  - `refined_text_fill_plan.json` and `refined_image_plan.json` produce `image_generation_plan.json`.
  - Generated image is copied into the current run `generated_images` directory.
  - `post_images` applies text, inserts the image, and writes audit reports.

### smoke02: Non-Table Image Slot Recognition

- Scope:
  - Paragraph blank region recognized as a possible image area.
- Verified at that stage:
  - Unsupported execution did not randomly insert the image.
  - The slot was recorded as unresolved instead of corrupting layout.

### smoke03: `paragraph_blank_region` Insertion

- Scope:
  - Non-table screenshot slot with anchor/range metadata.
- Verified:
  - `paragraph_blank_region` can be inserted for the minimum supported case.
  - `inserted_images = 1`.
  - `unresolved_image_insert = 0`.

### smoke04: 13-Image High Count Threshold

- Scope:
  - 13 screenshot slots.
- Verified:
  - `expected_image_count = 13`.
  - The workflow triggers `confirm_threshold`.
  - The plan preserves one slot to one image.
  - The workflow does not force a four-image merge merely to reduce count.

### smoke06 / smoke04 Regression After Fixes

- Verified:
  - `image_count_confirmation.json` is usable.
  - `post_images` no longer repeats the high-count block after valid confirmation.
  - Fixed table row height can be cleared or relaxed before screenshot insertion.
  - Screenshots are no longer obviously cropped in supported table-cell cases.
  - Image quality audit does not incorrectly fail valid dark HCL console screenshots.
  - Output filename slug de-duplication works.

## Formal Samples

### Experiment 13 NAT Configuration

- Scope:
  - Text fills.
  - Multi-stage HCL screenshots.
  - NAT result explanations.
- Current status:
  - Basic NAT, NAPT, Easy IP, and NAT Server flow is basically usable.
  - Dynamic image count and current-run image isolation worked.
  - Identity fields remained unfilled by default.

### Experiment 14 WAN Basics

- Scope:
  - HDLC.
  - PPP.
  - PAP.
  - CHAP.
  - 30 command-line screenshots.
- Current status:
  - High-count confirmation worked.
  - One screenshot per required table slot worked.
  - Current-run image isolation worked.
  - The task-specific requirement to generate command-line-only screenshots was handled through semantic image planning.

## Not Fully Verified Yet

- Full DataGrip database report workflow.
- Long text block generation and insertion, including:
  - experiment summaries,
  - result analysis,
  - thinking questions,
  - multi-step code plus explanation blocks.
- Paragraph anchors inside table cells.
- Batch identity field replacement.
- Formal natural-language experiment type recognition when no smoke-test hook sentence is present.
