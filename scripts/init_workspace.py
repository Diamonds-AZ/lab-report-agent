from pathlib import Path
import shutil
import sys


def copy_if_missing(src: Path, dst: Path):
    if dst.exists() and dst.stat().st_size > 0:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main():
    workspace = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    skill_root = Path(__file__).resolve().parents[1]
    defaults = skill_root / "assets" / "default_configs"

    dirs = [
        "input",
        "output/reports",
        "output/images",
        "output/checks",
        "assets/references/hcl",
        "assets/references/datagrip",
        "assets/references/idea",
        "assets/references/vscode",
        "assets/common",
        "configs/profiles",
        "work",
    ]
    for rel in dirs:
        (workspace / rel).mkdir(parents=True, exist_ok=True)

    created = []
    for src in defaults.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(defaults)
        if copy_if_missing(src, workspace / "configs" / rel):
            created.append(str(Path("configs") / rel))

    print(f"workspace={workspace}")
    print("created_defaults=" + ",".join(created))


if __name__ == "__main__":
    main()
