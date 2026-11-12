# Testing Notes

## Draft Validation

The draft skill was validated with:

```text
python quick_validate.py work/skill_draft/lab-report-agent
```

Result:

```text
Skill is valid!
```

## Cross-Workspace Smoke Test

Test workspace:

```text
output/checks/skill_full_test/
```

Steps executed:

1. `scripts/init_workspace.py`
2. Copied `input/template.docx`
3. `scripts/analyze_template.py`
4. `scripts/extract_doc_structure.py`
5. `scripts/extract_text_fill_candidates.py`
6. Codex/GPT semantic review writes `work/refined_text_fill_plan.json`
7. `scripts/apply_text_fill_plan.py`
8. `scripts/audit_report.py`

Generated:

- `work/report_analysis.md`
- `work/doc_structure.json`
- `work/draft_text_fill_candidates.json`
- `work/refined_text_fill_plan.json`
- `work/blank_fill_audit.md`
- `work/batch_check_report.md`
- `output/reports/skill_full_test_report.docx`

## Known Scope

- The candidate extraction script is deterministic. Codex/GPT semantic review must produce `refined_text_fill_plan.json`; scripts must not silently promote draft candidates into a final plan.
- Image generation itself is performed by Codex/image tooling, not by a bundled script. `build_image_prompts.py` prepares prompt records.
- DOCX visual render QA depends on the host having a working Word/LibreOffice rendering path.

## Smoke Regression Matrix

- `01_smoke_single_fill_single_table_image.docx`: single text fill, one table-cell image slot, HCL run isolation, basic audit.
- `02_non_table_image_slot.docx`: non-table `paragraph_blank_region` screenshot slot; after the third-round fix this should insert one image below the anchor and leave `unresolved_image_insert=0`.
- `03_smoke_chinese_path_docx.docx`: Chinese workspace path, Chinese input filename, Chinese output filename, no new `???` or `�`.
- `04_smoke_chinese_path_doc.doc`: Chinese workspace path, legacy `.doc` conversion, conversion stdout does not pollute parent process paths.
- `05_smoke_blank_variants.docx`: underline placeholder, standalone-space run, sentence-middle spaces, multiple blanks in one paragraph, mixed underline and spaces.
- `06_smoke_missing_image_hard_fail.docx`: current run expects one image, current run image is missing, legacy images exist elsewhere, `post_images` must fail without fallback.
- `08_legacy_doc_converter_fallback`: metadata check for the fixed converter order: `.doc` uses LibreOffice / `soffice`, WPS COM on Windows, then Microsoft Word COM, with no implicit fallback to stale `input/template.docx`.

## Portable Converter Tests

Run the converter unit tests without requiring an installed office suite:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

These tests validate converter ordering, isolated LibreOffice profile arguments, and rejection of malformed DOCX output. They do not prove that LibreOffice, WPS, or Word is installed on the current computer. For an actual legacy-document conversion, install LibreOffice or a supported Windows COM application and run a real `.doc` conversion; record the machine and converter in the test notes.
