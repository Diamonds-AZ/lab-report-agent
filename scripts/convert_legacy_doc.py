from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile
from utils.file_io import write_json


def converter_result(path: Path | None, mode: str, detail: str) -> tuple[Path | None, dict]:
    return path, {"converter": mode, "detail": detail, "success": path is not None}


def read_local_soffice_path() -> str | None:
    config_path = local_config_path()
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        key, separator, value = line.partition("=")
        if separator and key.strip() == "LAB_REPORT_SOFFICE_PATH":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value:
                return value
    return None


def local_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / ".env"


def resolve_soffice_path(value: str) -> Path | None:
    candidate = Path(value.strip().strip('"')).expanduser()
    if candidate.is_dir():
        names = ("soffice.com", "soffice.exe") if os.name == "nt" else ("soffice",)
        candidates = [candidate / "program" / name for name in names]
        candidates.extend(candidate / name for name in names)
        candidate = next((item for item in candidates if item.is_file()), candidates[0])
    if not candidate.is_file():
        return None
    if os.name == "nt" and candidate.name.lower() not in ("soffice.com", "soffice.exe"):
        return None
    return candidate.resolve()


def configure_soffice_path(value: str) -> Path:
    resolved = resolve_soffice_path(value)
    if resolved is None:
        raise ValueError("Path must point to soffice.com/soffice.exe or a LibreOffice installation folder containing program/soffice.exe.")
    config_path = local_config_path()
    existing = config_path.read_text(encoding="utf-8").splitlines() if config_path.exists() else []
    key = "LAB_REPORT_SOFFICE_PATH"
    replacement = f'{key}="{resolved}"'
    updated = []
    found = False
    for line in existing:
        current_key, separator, _ = line.partition("=")
        if separator and current_key.strip() == key:
            if not found:
                updated.append(replacement)
                found = True
        else:
            updated.append(line)
    if not found:
        updated.append(replacement)
    config_path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
    return resolved


def find_soffice() -> str | None:
    configured = os.environ.get("LAB_REPORT_SOFFICE_PATH")
    if not configured:
        configured = read_local_soffice_path()
    if configured:
        resolved = resolve_soffice_path(configured)
        if resolved:
            return str(resolved)

    executable_names = ("soffice.com", "soffice.exe", "soffice") if os.name == "nt" else ("soffice",)
    for name in executable_names:
        found = shutil.which(name)
        if found:
            return found

    return None


def find_bundled_python_home(soffice: str) -> str | None:
    program_dir = Path(soffice).resolve().parent
    for candidate in program_dir.glob("python-core-*"):
        if (candidate / "lib" / "os.py").is_file():
            return str(candidate)
    return None


def is_valid_docx(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            return (
                archive.testzip() is None
                and "[Content_Types].xml" in names
                and "word/document.xml" in names
            )
    except (OSError, zipfile.BadZipFile):
        return False


def clear_output(path: Path, converter: str) -> dict | None:
    if not path.exists():
        return None
    try:
        path.unlink()
        return None
    except OSError as exc:
        return converter_result(None, converter, f"{converter}_output_unlink_failed: {exc}")[1]


def create_isolated_profile(out_dir: Path) -> Path:
    # LibreOffice on Windows can crash when its file URL for UserInstallation
    # becomes too long. Keep the profile name short and prefer the task folder;
    # fall back to its parent or the OS temp folder only when needed.
    parents = (out_dir, out_dir.parent, Path(tempfile.gettempdir()))
    for parent in parents:
        profile = parent / f".lo-{uuid.uuid4().hex[:12]}"
        try:
            if len(profile.as_uri()) >= 240:
                continue
            profile.mkdir()
            return profile
        except (OSError, ValueError):
            continue
    raise OSError("Could not create a short isolated LibreOffice profile path.")


def convert_with_soffice(input_path: Path, out_dir: Path):
    soffice = find_soffice()
    if not soffice:
        return converter_result(None, "soffice", "soffice_not_found")
    candidate = out_dir / (input_path.stem + ".docx")
    failure = clear_output(candidate, "soffice")
    if failure:
        return None, failure
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        profile = create_isolated_profile(out_dir)
    except OSError as exc:
        return converter_result(None, "soffice", f"soffice_profile_create_failed: {exc}")
    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nodefault",
        "--nolockcheck",
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
        python_home = find_bundled_python_home(soffice)
        if python_home:
            env["PYTHONHOME"] = python_home
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            proc = subprocess.run(
                [*cmd[:1], f"-env:UserInstallation={profile.as_uri()}", *cmd[1:]],
                stdout=stdout,
                stderr=stderr,
                timeout=90,
                env=env,
            )
            stdout.seek(0)
            stderr.seek(0)
            proc.stdout = stdout.read().decode("utf-8", errors="replace")
            proc.stderr = stderr.read().decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return converter_result(None, "soffice", "soffice_timeout")
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "unknown soffice failure")[-500:]
        return converter_result(None, "soffice", f"soffice_failed: {detail}")
    if candidate.exists():
        if is_valid_docx(candidate):
            return converter_result(candidate, "soffice", "legacy_doc_converted_soffice")
        candidate.unlink(missing_ok=True)
        return converter_result(None, "soffice", "soffice_invalid_docx_output")
    return converter_result(None, "soffice", "soffice_no_output")


def powershell_command() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("powershell")


def convert_with_com(input_path: Path, out_dir: Path, prog_id: str, converter: str, success_mode: str):
    if os.name != "nt":
        return converter_result(None, converter, f"{converter}_not_windows")
    powershell = powershell_command()
    if not powershell:
        return converter_result(None, converter, "powershell_not_found")

    output_path = out_dir / (input_path.stem + ".docx")
    failure = clear_output(output_path, converter)
    if failure:
        return None, failure

    script = r"""
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject $env:LAB_REPORT_OFFICE_PROG_ID
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($env:LAB_REPORT_WORD_INPUT_PATH, $false, $true)
    $doc.SaveAs2($env:LAB_REPORT_WORD_OUTPUT_PATH, 16)
}
finally {
    try {
        if ($doc -ne $null) {
            try {
                $doc.Close($false)
            }
            finally {
                [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc)
            }
        }
    }
    finally {
        if ($word -ne $null) {
            try {
                $word.Quit()
            }
            finally {
                [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
            }
        }
    }
}
"""
    cmd = [
        powershell,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["LAB_REPORT_OFFICE_PROG_ID"] = prog_id
    env["LAB_REPORT_WORD_INPUT_PATH"] = str(input_path)
    env["LAB_REPORT_WORD_OUTPUT_PATH"] = str(output_path)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, env=env)
    except subprocess.TimeoutExpired:
        return converter_result(None, converter, f"{converter}_timeout")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or f"unknown {converter} failure")[-500:]
        return converter_result(None, converter, f"{converter}_failed: {detail}")
    if output_path.exists():
        if is_valid_docx(output_path):
            return converter_result(output_path, converter, success_mode)
        output_path.unlink(missing_ok=True)
        return converter_result(None, converter, f"{converter}_invalid_docx_output")
    return converter_result(None, converter, f"{converter}_no_output")


def convert_with_wps_com(input_path: Path, out_dir: Path):
    return convert_with_com(input_path, out_dir, "Kwps.Application", "wps_com", "legacy_doc_converted_wps_com")


def convert_with_word_com(input_path: Path, out_dir: Path):
    return convert_with_com(input_path, out_dir, "Word.Application", "word_com", "legacy_doc_converted_word_com")


def resolve_legacy_doc(input_path: Path, out_dir: Path) -> tuple[Path | None, str | None, list[dict]]:
    attempts = []
    for converter in (convert_with_soffice, convert_with_wps_com, convert_with_word_com):
        converted, attempt = converter(input_path, out_dir)
        attempts.append(attempt)
        if converted:
            return converted, attempt["detail"], attempts
    return None, None, attempts


def converter_status() -> dict:
    soffice = find_soffice()
    status = {
        "soffice": {"found": soffice is not None, "path": soffice},
        "wps_com": {"supported_on_this_os": os.name == "nt", "registered": None, "activation_tested": False},
        "word_com": {"supported_on_this_os": os.name == "nt", "registered": None, "activation_tested": False},
    }
    if os.name == "nt":
        import winreg

        for key, prog_id in (("wps_com", "Kwps.Application"), ("word_com", "Word.Application")):
            try:
                winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id).Close()
                status[key]["registered"] = True
            except OSError:
                status[key]["registered"] = False
            status[key]["prog_id"] = prog_id
            status[key]["note"] = "COM activation is tested only when a conversion runs."
    return status


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--configure-soffice":
        if len(sys.argv) != 3:
            raise SystemExit("Usage: convert_legacy_doc.py --configure-soffice <soffice-path-or-install-folder>")
        try:
            configured_path = configure_soffice_path(sys.argv[2])
        except (OSError, ValueError) as exc:
            raise SystemExit(f"Could not configure LibreOffice: {exc}") from exc
        print(f"LibreOffice path saved for future tasks: {configured_path}")
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        status = converter_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
        has_registered_com = any(item.get("registered") is True for item in status.values())
        raise SystemExit(0 if status["soffice"]["found"] or has_registered_com else 2)

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
                "legacy .doc conversion failed; provide a .docx template or install LibreOffice, WPS Office, or Microsoft Word. "
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
