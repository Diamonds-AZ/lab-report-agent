# Contributing

Thanks for helping improve `lab-report-agent`.

Before opening a pull request:

1. Keep changes scoped to the skill, scripts, docs, schemas, or sanitized smoke fixtures.
2. Do not include private templates, generated reports, generated screenshots, rosters, or local workspace artifacts.
3. Run:

```powershell
python tests\smoke\run_smoke_asset_checks.py
```

4. Update docs or smoke fixtures when changing confirmation gates, image-source policy, text-fill behavior, or audit rules.

The project intentionally keeps semantic decisions in Codex/GPT and leaves scripts responsible for structure extraction, execution, and auditing.
