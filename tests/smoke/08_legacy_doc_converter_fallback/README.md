# Legacy DOC Converter Fallback

Metadata-only smoke case for the fixed `.doc` input conversion contract.

Expected behavior:

- Native `.docx` inputs are used directly.
- Legacy `.doc` inputs try LibreOffice / `soffice` first.
- On Windows, WPS COM is tried after LibreOffice; Microsoft Word COM is the next fallback.
- If all converters fail, the workflow stops with `ACTION_REQUIRED`.
- A stale `input/template.docx` must never be used as an implicit fallback for a failed `.doc` conversion.

