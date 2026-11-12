# First-Run Environment Setup

Use this guide when a user runs the skill for the first time on a Windows computer or when the current machine is unfamiliar.

## 1. Inspect Before Installing

After identifying the supplied template, run the read-only check from the skill directory:

```powershell
python scripts\setup_environment.py --input "<template-path>" --json
```

The check reports Python version, `python-docx`, Pillow, and available legacy `.doc` converters. A `.docx` task does not require an office converter. Image generation availability is provided by Codex and cannot be determined by this local script. The experiment software is task-specific and is not bundled with this skill.

If Python is unavailable, explain that the scripts cannot run yet and offer to install Python 3.11+ from the official Python distribution. Do not install it without the user's approval.

## 2. Install Python Dependencies In Isolation

If Python is 3.11+ but package dependencies are missing, explain what will be installed and ask permission. After approval, create the environment in the task workspace (not in the skill installation directory):

```powershell
python scripts\setup_environment.py --install-python-deps --venv "<workspace>\.venv"
```

Use the resulting interpreter for all skill scripts in this task:

```text
<workspace>\.venv\Scripts\python.exe
```

The setup helper refuses to modify a non-empty target directory. It only installs the dependencies listed in this repository's `requirements.txt`; it does not install Python itself, office software, experiment software, or image-generation tools.

## 3. Resolve LibreOffice For Conversion And Rendering

Before the first document render on a machine, and whenever a legacy `.doc` needs conversion, check whether LibreOffice is available on `PATH` or in the saved skill configuration. Rendering needs LibreOffice even when the input is already `.docx`.

1. Tell the user LibreOffice was not found. Ask once whether they can provide the path to `soffice.com` / `soffice.exe` or its installation folder, use an available WPS/Word fallback for conversion, or provide a `.docx` template instead. Do not silently choose a COM fallback on first use.
2. When the user provides a path, run `scripts/convert_legacy_doc.py --configure-soffice "<path>"`. The command validates the executable and saves the path in the skill's local `.env`; this is the user's requested persistent preference, so do not ask separately to remember it. Rerun the converter check and use the saved path for conversion and later tasks. For `render_docx.py`, prepend the saved executable's parent folder to the child process's `PATH` so the renderer resolves the same LibreOffice. Do not alter the machine-wide `PATH`.
3. If the user chooses installation, use the official LibreOffice distribution and let the user choose the destination. Never assume a drive letter or reuse a path from another computer. Ask before downloading or launching an installer.
4. Re-run the check and, when feasible, perform a real conversion test on a copy of the provided `.doc`. Accept the setup only if the generated DOCX is valid.

WPS and Microsoft Word COM are optional Windows fallbacks. A registered COM ProgID is only a discovery hint; actual availability is proven by a successful conversion, not by registry presence. On Windows, the check reads `HKEY_CLASSES_ROOT\Kwps.Application` and `HKEY_CLASSES_ROOT\Word.Application` to see whether those ProgIDs are registered. It does not launch either application during the check.

## 4. Experiment Software And Screenshots

Do not install experiment-specific applications preemptively. Determine whether the task needs a real application, whether it is already installed, and what evidence the user expects. Ask before downloading or installing any application. Follow the image source the user or confirmed task plan selected. Generated images should look like normal requested report images; do not add visible AI labels, illustration labels, watermarks, or explanatory marks unless the user explicitly requests them. Keep source provenance in the internal manifest and audit. If the user requires real software evidence and no real capture is available, stop and ask for a screenshot or approval to prepare the software; do not propose a visibly labeled generated image as a substitute.

## 5. Recovery

- If dependency installation fails, report the error and offer manual installation or a supported Python environment; do not keep retrying automatically.
- If `.doc` conversion fails, preserve the original, record the converter attempts, then ask for a `.docx` copy or approval to repair/install a converter.
- If only image generation is unavailable, explain that this depends on the active Codex environment and offer manual screenshots or another explicitly supported source.
