# Legacy DOC Converter Fallback

Metadata-only smoke case for the fixed `.doc` input conversion contract.

Expected behavior:

- Native `.docx` inputs are used directly.
- Legacy `.doc` inputs try LibreOffice / `soffice` first.
- On Windows, Microsoft Word COM automation is the fallback converter when `soffice` is unavailable or fails.
- If all converters fail, the workflow stops with `ACTION_REQUIRED`.
- A stale `input/template.docx` must never be used as an implicit fallback for a failed `.doc` conversion.

