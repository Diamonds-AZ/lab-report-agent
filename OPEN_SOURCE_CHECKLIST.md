# Open Source Release Checklist

Use this checklist before pushing the repository to a public GitHub repo.

- [ ] Confirm no real student reports are present.
- [ ] Confirm no real course templates are present unless redistribution is allowed.
- [ ] Confirm `input/`, `output/`, and `work/` are not tracked.
- [ ] Confirm rosters and identity-bearing configs are not tracked.
- [ ] Confirm generated screenshots are not tracked.
- [ ] Confirm no API keys, tokens, local usernames, WeChat paths, or absolute personal paths are present.
- [ ] Confirm the included smoke fixture documents are synthetic or redistribution-safe.
- [ ] Run `python tests\smoke\run_smoke_asset_checks.py`.
- [ ] Choose whether MIT is the intended license.
- [ ] Review `README.md` for accurate limitations and dependency notes.
