# 03 Question Area Not Insert

Purpose: verify that images are not inserted into long question/reference text just because it contains phrases like "下图", "如下图", or "观察".

Fixture idea:

- The Word template contains a long question/reference area with "如下图所示".
- Later it contains an answer divider: "实验报告模板".
- Only the area after the answer divider may receive generated images.

Expected behavior:

- GPT/Codex classifies the long requirement area as `question_area` or `reference_material`.
- Planned images in those zones fail validation unless explicitly allowed.
- Second-stage confirmation table shows `zone_type`.
