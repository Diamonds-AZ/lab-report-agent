import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "setup_environment.py"
SPEC = importlib.util.spec_from_file_location("setup_environment", SCRIPT)
setup_environment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup_environment)


class SetupEnvironmentTests(unittest.TestCase):
    def test_missing_libreoffice_prompts_before_registered_com_fallback(self):
        converter_status = {
            "soffice": {"found": False, "path": None},
            "wps_com": {"registered": True},
            "word_com": {"registered": False},
        }
        with patch.object(
            setup_environment.subprocess,
            "run",
            return_value=Mock(stdout=json.dumps(converter_status), stderr=""),
        ), patch.object(Path, "is_file", return_value=True):
            result = setup_environment.check_environment(Path("template.doc"))

        self.assertTrue(result["ready"])
        self.assertTrue(any("ask whether the user can provide" in note for note in result["notes"]))

    def test_refuses_nonempty_unmanaged_environment(self):
        target = Path("C:/fake/lab-report-env")
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "iterdir", return_value=iter([Path("keep.txt")])), \
             patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Refusing to modify"):
                setup_environment.setup_python_environment(target)

    def test_explicit_setup_creates_managed_venv_and_installs_repo_requirements(self):
        target = Path("C:/fake/lab-report-env")
        with patch.object(Path, "exists", return_value=False), \
             patch.object(Path, "write_text") as write_marker, \
             patch.object(setup_environment.subprocess, "run") as run:
            result = setup_environment.setup_python_environment(target)

        self.assertEqual(result, target.resolve() / "Scripts" / "python.exe")
        write_marker.assert_called_once()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0][-5:], ["-m", "pip", "install", "-r", str(setup_environment.REQUIREMENTS)])


if __name__ == "__main__":
    unittest.main()
