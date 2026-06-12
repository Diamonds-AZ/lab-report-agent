from pathlib import Path
import json
import shutil
import subprocess
import sys
import os
from utils.file_io import write_json


def convert_with_soffice(input_path: Path, out_dir: Path):
    soffice = shutil.which("soffice")
    if not soffice:
        return None, "soffice_not_found"
    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        "docx",
        "--outdir",
        str(out_dir),
        str(input_path),
    ]
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, env=env)
    except subprocess.TimeoutExpired:
        return None, "soffice_timeout"
    if proc.returncode != 0:
        return None, f"soffice_failed: {proc.stderr[-500:]}"
    candidate = out_dir / (input_path.stem + ".docx")
    if candidate.exists():
        return candidate, "legacy_doc_converted"
    return None, "soffice_no_output"


def main():
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    input_path = Path(sys.argv[2]) if len(sys.argv) > 2 else workspace / "input" / "template.docx"
    if not input_path.is_absolute():
        input_path = workspace / input_path
    out_dir = workspace / "input"
    audit_path = workspace / "work" / "input_resolution.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "original_input": str(input_path),
        "resolved_input": None,
        "mode": None,
        "notes": [],
    }

    if input_path.suffix.lower() == ".docx" and input_path.exists():
        result.update({"resolved_input": str(input_path), "mode": "native_docx"})
    elif input_path.suffix.lower() == ".doc" and input_path.exists():
        converted, mode = convert_with_soffice(input_path, out_dir)
        if converted:
            result.update({"resolved_input": str(converted), "mode": mode})
        else:
            fallback = workspace / "input" / "template.docx"
            if fallback.exists():
                result.update({"resolved_input": str(fallback), "mode": "fallback_existing_docx"})
                result["notes"].append(f"legacy .doc conversion failed: {mode}; using existing input/template.docx")
            else:
                result.update({"resolved_input": None, "mode": "legacy_doc_unresolved"})
                result["notes"].append(f"legacy .doc conversion failed: {mode}; no fallback docx found")
    else:
        result.update({"resolved_input": None, "mode": "input_missing"})

    write_json(audit_path, result)
    print(result.get("resolved_input") or "")
    print(audit_path)
    if not result.get("resolved_input"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
