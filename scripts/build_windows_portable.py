"""Build a Windows x64 portable ZIP; run with a Windows Python 3.12 x64."""
from __future__ import annotations

import hashlib
import importlib.metadata
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
NAME = "TeltonikaModbusConfigurator"


def main() -> None:
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit("Build this package using Windows x64 Python.")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--windowed", "--noupx", "--name", NAME,
        "--paths", str(ROOT / "src"), "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "pyinstaller"),
        "--specpath", str(ROOT / "build"), str(ROOT / "packaging" / "launcher.py"),
    ], cwd=ROOT, check=True)
    bundle = ROOT / "dist" / NAME
    for filename in ("README.md", "LICENSE", "CHANGELOG.md"):
        shutil.copy2(ROOT / filename, bundle / filename)
    shutil.copy2(ROOT / "packaging" / "PORTABLE_README.txt", bundle / "START_HERE.txt")
    shutil.copytree(ROOT / "examples", bundle / "examples", dirs_exist_ok=True)
    (bundle / "VERSION.txt").write_text(version + "\n", encoding="utf-8")
    licenses = bundle / "third_party_licenses"
    for distribution in importlib.metadata.distributions():
        for item in distribution.files or ():
            if any(token in str(item).lower() for token in ("license", "copying", "notice")) and ".dist-info/" in str(item):
                source = Path(distribution.locate_file(item))
                if source.is_file():
                    target = licenses / distribution.metadata["Name"] / str(item)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    # Smoke-test the actual frozen executable before distributing it.
    subprocess.run([str(bundle / (NAME + ".exe")), "--smoke-test"], cwd=bundle, check=True, timeout=90)
    archive = ROOT / "dist" / f"{NAME}-{version}-windows-x64-portable"
    zip_path = Path(shutil.make_archive(str(archive), "zip", root_dir=bundle.parent, base_dir=NAME))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    zip_path.with_suffix(".zip.sha256").write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    print(f"Portable ZIP: {zip_path}")


if __name__ == "__main__":
    main()
