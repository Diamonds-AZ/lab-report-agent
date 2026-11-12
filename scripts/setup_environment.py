"""Check report-generation prerequisites and optionally prepare an isolated Python environment."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"


def check_environment(input_path: Path | None = None) -> dict:
    python_ok = sys.version_info >= (3, 11)
    packages = {}
    for distribution in ("python-docx", "Pillow"):
        try:
            packages[distribution] = {"installed": True, "version": importlib.metadata.version(distribution)}
        except importlib.metadata.PackageNotFoundError:
            packages[distribution] = {"installed": False, "version": None}

    converter_process = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "convert_legacy_doc.py"), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        converters = json.loads(converter_process.stdout)
    except json.JSONDecodeError:
        converters = {"check_error": converter_process.stderr.strip() or converter_process.stdout.strip()}

    needs_converter = input_path is not None and input_path.suffix.lower() == ".doc"
    input_exists = input_path is None or input_path.is_file()
    converter_available = bool(
        converters.get("soffice", {}).get("found")
        or converters.get("wps_com", {}).get("registered")
        or converters.get("word_com", {}).get("registered")
    )
    ready = input_exists and python_ok and all(item["installed"] for item in packages.values())
    if needs_converter:
        ready = ready and converter_available

    notes = [
        "Image generation is provided by the active Codex environment and cannot be checked by this local script.",
        "A real experiment application is task-specific and is not installed by this setup helper.",
    ]
    if needs_converter and not converters.get("soffice", {}).get("found"):
        notes.append(
            "LibreOffice was not found on PATH or at an explicit path. On first use, ask whether the user can provide its executable path before selecting a Windows COM fallback."
        )

    return {
        "ready": ready,
        "python": {"version": ".".join(map(str, sys.version_info[:3])), "minimum": "3.11", "ok": python_ok},
        "packages": packages,
        "input": str(input_path) if input_path else None,
        "input_exists": input_exists,
        "legacy_doc_converter_required": needs_converter,
        "legacy_doc_converter_available": converter_available,
        "converters": converters,
        "notes": notes,
    }


def setup_python_environment(venv_path: Path) -> Path:
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required to create the environment.")
    venv_path = venv_path.expanduser().resolve()
    marker = venv_path / ".lab-report-agent-venv"
    if venv_path.exists() and any(venv_path.iterdir()):
        if not marker.is_file():
            raise RuntimeError(f"Refusing to modify a non-empty environment path: {venv_path}")
    else:
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        marker.write_text("lab-report-agent managed environment\n", encoding="utf-8")
    python = venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)], check=True)
    return python


def main() -> int:
    parser = argparse.ArgumentParser(description="Check prerequisites or prepare an isolated Python environment.")
    parser.add_argument("--input", type=Path, help="Template path; .doc requires a working local converter.")
    parser.add_argument("--install-python-deps", action="store_true", help="Create a venv and install this skill's Python dependencies.")
    parser.add_argument("--venv", type=Path, help="Environment path required with --install-python-deps.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    if args.install_python_deps:
        if not args.venv:
            parser.error("--venv is required with --install-python-deps")
        try:
            python = setup_python_environment(args.venv)
        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            print(f"Python environment setup failed: {exc}", file=sys.stderr)
            return 1
        print(f"Python environment ready: {python}")
        return 0
    if args.venv:
        parser.error("--venv is only used with --install-python-deps")

    result = check_environment(args.input)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Ready for this input: {'yes' if result['ready'] else 'no'}")
        print(f"Python {result['python']['version']} (need >= {result['python']['minimum']}): {'OK' if result['python']['ok'] else 'missing/too old'}")
        if not result["input_exists"]:
            print("Template: not found")
        for name, package in result["packages"].items():
            state = package["version"] if package["installed"] else "missing"
            print(f"{name}: {state}")
        if result["legacy_doc_converter_required"]:
            print(f"Legacy .doc converter available: {'yes' if result['legacy_doc_converter_available'] else 'no'}")
        elif args.input:
            print("Office converter: not required for this input")
        for note in result["notes"]:
            print(f"Note: {note}")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
