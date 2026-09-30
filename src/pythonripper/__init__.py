from pathlib import Path
import tomllib


def __get_app_version() -> str:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    version = data["project"]["version"]
    if not isinstance(version, str):
        raise
    return f"v{version}"


__version__ = __get_app_version()
__icon__ = Path(__file__).resolve().parents[2] / "img" / "icon.jpg"
