# Encoding Policy

## Encoding

All text, JSON, Markdown, and YAML files must be read and written as UTF-8.

Use `scripts/utils/file_io.py` for file access:

- `read_text`
- `write_text`
- `read_json`
- `write_json`
- `read_yaml_text`

JSON writes must use `ensure_ascii=False`.

Child Python processes must run with:

- `PYTHONIOENCODING=utf-8`
- `PYTHONUTF8=1`

When stdout/stderr is captured, use `text=True`, `encoding="utf-8"`, and `errors="replace"`.

## Prohibited Patterns

- Do not embed long Chinese content in PowerShell here-strings.
- Do not embed Chinese filesystem paths in PowerShell here-strings, PowerShell pipes, `python -c`, or temporary inline Python snippets.
- Do not pipe large Chinese prompts or report paragraphs into Python.
- Do not pipe complex JSON plans into Python; write them as UTF-8 files and pass a path.
- Do not rewrite whole Word paragraphs from shell-transmitted Chinese strings.
- Do not continue editing an output `.docx` after encoding pollution is detected.

## Required Checks

`run_lab_report_task.py` writes:

- `work/encoding_report.md`

`audit_report.py` compares input and output counts for:

- `???`
- `�`

If output has more of either marker than input, the report is polluted and must be regenerated from a clean template.
