"""Download Linux (manylinux x86_64, CPython 3.12) wheels for the shared Lambda layer.

Builds without Docker, so it works on Windows: pip fetches prebuilt Linux wheels
instead of compiling anything locally.

    python scripts/build_layer.py      # then: sam build && sam deploy
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "layers" / "requirements.txt"
TARGET = ROOT / ".layers" / "deps" / "python"


def main() -> None:
    shutil.rmtree(TARGET.parent, ignore_errors=True)
    TARGET.mkdir(parents=True)
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "--quiet",
            "--platform", "manylinux2014_x86_64",
            "--implementation", "cp",
            "--python-version", "3.12",
            "--only-binary=:all:",
            "--target", str(TARGET),
            "-r", str(REQUIREMENTS),
        ],
        check=True,
    )  # fmt: skip
    print(f"Layer ready at {TARGET.parent}")


if __name__ == "__main__":
    main()
