from __future__ import annotations

from pathlib import Path
import shutil
import stat
import sys


def configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def make_writable(path: str | Path) -> bool:
    target = Path(path)
    if not target.exists():
        return False
    try:
        target.chmod(target.stat().st_mode | stat.S_IWRITE)
        return True
    except OSError:
        return False


def copy_template_to_input(src: str | Path, dst: str | Path) -> dict:
    source = Path(src)
    target = Path(dst)
    if not source.exists():
        raise FileNotFoundError(f"Input template does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    readonly_removed = make_writable(target)
    return {
        "source": str(source),
        "destination": str(target),
        "copied": True,
        "readonly_removed": readonly_removed,
        "is_writable": is_writable_file(target),
    }


def safe_delete_file(path: str | Path) -> None:
    target = Path(path)
    if not target.exists():
        return
    make_writable(target)
    target.unlink()


def safe_clean_dir(path: str | Path, keep_dir: bool = True) -> None:
    target = Path(path)
    if not target.exists():
        if keep_dir:
            target.mkdir(parents=True, exist_ok=True)
        return

    make_writable(target)
    for child in list(target.iterdir()):
        if child.is_dir():
            safe_clean_dir(child, keep_dir=False)
            make_writable(child)
            child.rmdir()
        else:
            safe_delete_file(child)

    if keep_dir:
        target.mkdir(parents=True, exist_ok=True)


def is_writable_file(path: str | Path) -> bool:
    target = Path(path)
    if not target.exists():
        return False
    try:
        make_writable(target)
        with target.open("ab"):
            pass
        return True
    except OSError:
        return False


def assert_output_path_writable(path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        make_writable(target)
        try:
            with target.open("ab"):
                pass
        except PermissionError as exc:
            raise RuntimeError(
                f"输出文件不可写，可能被 Word/WPS 打开或文件仍为只读：{target}"
            ) from exc
        except OSError as exc:
            raise RuntimeError(f"输出文件不可写：{target}") from exc

    test_file = target.parent / ".write_test.tmp"
    try:
        test_file.write_text("ok", encoding="utf-8")
        make_writable(test_file)
        test_file.unlink()
    except PermissionError as exc:
        raise RuntimeError(
            f"输出目录不可写，请检查目录权限或关闭占用文件：{target.parent}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"输出目录不可写：{target.parent}") from exc
