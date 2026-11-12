import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import convert_legacy_doc as converter


def write_minimal_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")


class LegacyDocConverterTests(unittest.TestCase):
    def setUp(self):
        self.out_dir = Path(__file__).resolve().parent
        self.source = self.out_dir / "__converter_test_input.doc"
        self.target = self.out_dir / "__converter_test_input.docx"
        self.target.unlink(missing_ok=True)

    def tearDown(self):
        self.target.unlink(missing_ok=True)

    def test_configured_windows_console_launcher_is_used_directly(self):
        program_dir = self.out_dir / "__test_soffice_selection"
        program_dir.mkdir(exist_ok=True)
        console_launcher = program_dir / "soffice.com"
        gui_executable = program_dir / "soffice.exe"
        console_launcher.touch()
        gui_executable.touch()

        try:
            with patch.dict(converter.os.environ, {"LAB_REPORT_SOFFICE_PATH": str(console_launcher)}), patch.object(
                converter.os, "name", "nt"
            ):
                self.assertEqual(converter.find_soffice(), str(console_launcher))
        finally:
            import shutil

            shutil.rmtree(program_dir, ignore_errors=True)

    def test_does_not_guess_custom_installation_directories(self):
        with patch.dict(converter.os.environ, {"LAB_REPORT_SOFFICE_PATH": ""}), patch.object(
            converter, "read_local_soffice_path", return_value=None
        ), patch.object(converter.shutil, "which", return_value=None):
            self.assertIsNone(converter.find_soffice())

    def test_reads_soffice_path_from_local_env_file(self):
        with patch.dict(converter.os.environ, {"LAB_REPORT_SOFFICE_PATH": ""}), patch.object(
            converter, "read_local_soffice_path", return_value=str(self.out_dir / "soffice.com")
        ), patch.object(Path, "is_file", return_value=True), patch.object(
            converter.shutil, "which", return_value=None
        ):
            self.assertEqual(converter.find_soffice(), str(self.out_dir / "soffice.com"))

    def test_soffice_output_is_validated_and_uses_isolated_profile(self):
        def fake_run(command, **_kwargs):
            write_minimal_docx(self.target)

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            profile_arg = next(arg for arg in command if arg.startswith("-env:UserInstallation=file:"))
            profile_uri = profile_arg.split("=", 1)[1]
            self.assertLess(len(profile_uri), 240)
            return Result()

        with patch.object(converter, "find_soffice", return_value="/usr/bin/soffice"), patch.object(
            converter.subprocess, "run", side_effect=fake_run
        ):
            converted, attempt = converter.convert_with_soffice(self.source, self.out_dir)

        self.assertEqual(converted, self.target)
        self.assertEqual(attempt["detail"], "legacy_doc_converted_soffice")
        self.assertTrue(converter.is_valid_docx(self.target))

    def test_long_output_path_uses_shorter_profile_parent(self):
        long_out_dir = self.out_dir / ("nested-" * 40)
        profile = converter.create_isolated_profile(long_out_dir)
        try:
            self.assertEqual(profile.parent, self.out_dir)
            self.assertLess(len(profile.as_uri()), 240)
        finally:
            import shutil

            shutil.rmtree(profile, ignore_errors=True)

    def test_soffice_uses_adjacent_bundled_python_home(self):
        program_dir = self.out_dir / "__test_soffice_program"
        python_home = program_dir / "python-core-3.12.13"
        (python_home / "lib").mkdir(parents=True, exist_ok=True)
        (python_home / "lib" / "os.py").touch()
        soffice = program_dir / "soffice.com"

        def fake_run(_command, **kwargs):
            write_minimal_docx(self.target)
            self.assertEqual(kwargs["env"]["PYTHONHOME"], str(python_home))

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        try:
            with patch.object(converter, "find_soffice", return_value=str(soffice)), patch.object(
                converter.subprocess, "run", side_effect=fake_run
            ):
                converted, attempt = converter.convert_with_soffice(self.source, self.out_dir)

            self.assertEqual(converted, self.target)
            self.assertEqual(attempt["detail"], "legacy_doc_converted_soffice")
        finally:
            import shutil

            shutil.rmtree(program_dir, ignore_errors=True)

    def test_invalid_output_is_rejected_and_removed(self):
        def fake_run(_command, **_kwargs):
            self.target.write_text("not a docx", encoding="utf-8")

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        with patch.object(converter, "find_soffice", return_value="soffice"), patch.object(
            converter.subprocess, "run", side_effect=fake_run
        ):
            converted, attempt = converter.convert_with_soffice(self.source, self.out_dir)

        self.assertIsNone(converted)
        self.assertEqual(attempt["detail"], "soffice_invalid_docx_output")
        self.assertFalse(self.target.exists())

    def test_resolver_stops_at_first_success(self):
        calls = []
        result_path = Path("converted.docx")

        def success(_source, _out_dir):
            calls.append("soffice")
            return result_path, {"converter": "soffice", "detail": "ok", "success": True}

        def should_not_run(_source, _out_dir):
            calls.append("fallback")
            return None, {"converter": "fallback", "detail": "not run", "success": False}

        with patch.object(converter, "convert_with_soffice", side_effect=success), patch.object(
            converter, "convert_with_wps_com", side_effect=should_not_run
        ), patch.object(converter, "convert_with_word_com", side_effect=should_not_run):
            converted, mode, attempts = converter.resolve_legacy_doc(Path("legacy.doc"), Path("input"))

        self.assertEqual(converted, result_path)
        self.assertEqual(mode, "ok")
        self.assertEqual(calls, ["soffice"])
        self.assertEqual(len(attempts), 1)


if __name__ == "__main__":
    unittest.main()
