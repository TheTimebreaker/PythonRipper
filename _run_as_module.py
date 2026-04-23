from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python run_as_module.py <path-to-file.py>")

    file_path = Path(sys.argv[1]).resolve()
    workspace_root = Path(__file__).resolve().parent

    try:
        rel = file_path.relative_to(workspace_root)
    except ValueError as error:
        raise SystemExit(f"{file_path} is not inside {workspace_root}") from error

    if rel.suffix != ".py":
        raise SystemExit("Selected file is not a .py file")

    module_name = ".".join(rel.with_suffix("").parts)

    # Make argv look like normal script execution
    sys.argv = [str(file_path), *sys.argv[2:]]

    runpy.run_module(module_name, run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
