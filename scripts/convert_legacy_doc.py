from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
from utils.file_io import write_json


def converter_result(path: Path | None, mode: str, detail: str) -> tuple[Path | None, dict]:
    return path, {"converter": mode, "detail": detail, "success": path is not None}


def convert_with_soffice(input_path: Path, out_dir: Path):
    soffice = shutil.which("soffice")
    if not soffice:
        return converter_result(None, "soffice", "soffice_not_found")
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
        return converter_result(None, "soffice", "soffice_timeout")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "unknown soffice failure")[-500:]
        return converter_result(None, "soffice", f"soffice_failed: {detail}")
    candidate = out_dir / (input_path.stem + ".docx")
    if candidate.exists():
        return converter_result(candidate, "soffice", "legacy_doc_converted_soffice")
    return converter_result(None, "soffice", "soffice_no_output")


def powershell_command() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("powershell")


def convert_with_word_com(input_path: Path, out_dir: Path):
    if os.name != "nt":
        return converter_result(None, "word_com", "word_com_not_windows")
    powershell = powershell_command()
    if not powershell:
        return converter_result(None, "word_com", "powershell_not_found")

    output_path = out_dir / (input_path.stem + ".docx")
    if output_path.exists():
        try:
            output_path.unlink()
        except OSError as exc:
            return converter_result(None, "word_com", f"word_com_output_unlink_failed: {exc}")

    script = r"""
param([string]$InputPath, [string]$OutputPath)
$ErrorActionPreference = 'Stop'
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($InputPath, $false, $true)
    $doc.SaveAs2($OutputPath, 16)
}
finally {
    if ($doc -ne $null) {
        $doc.Close($false)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc)
    }
    if ($word -ne $null) {
        $word.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
}
"""
    cmd = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
        str(input_path),
        str(output_path),
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=env)
    except subprocess.TimeoutExpired:
        return converter_result(None, "word_com", "word_com_timeout")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "unknown Word COM failure")[-500:]
        return converter_result(None, "word_com", f"word_com_failed: {detail}")
    if output_path.exists():
        return converter_result(output_path, "word_com", "legacy_doc_converted_word_com")
    return converter_result(None, "word_com", "word_com_no_output")


def resolve_legacy_doc(input_path: Path, out_dir: Path) -> tuple[Path | None, str | None, list[dict]]:
    attempts = []
    for converter in (convert_with_soffice, convert_with_word_com):
        converted, attempt = converter(input_path, out_dir)
        attempts.append(attempt)
        if converted:
            return converted, attempt["detail"], attempts
    return None, None, attempts


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
        "conversion_attempts": [],
    }

    if input_path.suffix.lower() == ".docx" and input_path.exists():
        result.update({"resolved_input": str(input_path), "mode": "native_docx"})
    elif input_path.suffix.lower() == ".doc" and input_path.exists():
        converted, mode, attempts = resolve_legacy_doc(input_path, out_dir)
        result["conversion_attempts"] = attempts
        if converted:
            result.update({"resolved_input": str(converted), "mode": mode})
        else:
            reasons = "; ".join(attempt["detail"] for attempt in attempts) or "no converter attempted"
            result.update({"resolved_input": None, "mode": "legacy_doc_unresolved"})
            result["notes"].append(
                "legacy .doc conversion failed; provide a .docx template or install LibreOffice/Microsoft Word. "
                f"attempts: {reasons}"
            )
    else:
        result.update({"resolved_input": None, "mode": "input_missing"})

    write_json(audit_path, result)
    print(result.get("resolved_input") or "")
    print(audit_path)
    if not result.get("resolved_input"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
