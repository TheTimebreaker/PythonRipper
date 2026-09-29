import platformdirs
from pydantic import BaseModel, Field
from pydantic_gui_settings_editor.types import DirectoryPath


class PathSettings(BaseModel):
    _user_config_path = platformdirs.PlatformDirs("PythonRipper", "TheTimebreaker").user_config_path
    downloads: DirectoryPath = Field(
        default=_user_config_path / "downloads",
        title="Download root directory",
        description=(
            "Choose a root directory, where all recently downloaded files are stored within.\n"
            "Files will be moved to 'storage' when processed (which will do file conversions and duplication checks)."
        ),
    )
    storage: DirectoryPath = Field(
        default=_user_config_path / "storage",
        title="Storage root directory",
        description=(
            "Choose a root directory, where all processed files are stored within.\n"
            "Files will be moved from 'downloads' to this when processed (which will do file conversions and duplication checks).\n"
            "Files can be moved further to 'archive', where files and filehashes can be stored, "
            "so they can still be referenced by duplication checks."
        ),
    )
    archive: DirectoryPath = Field(
        default=_user_config_path / "archive",
        title="Download root directory",
        description=(
            "Choose a root directory, where all archived files and filehashes are stored within.\n"
            "Files will be moved from 'storage' to this when archived, so they can still be referenced by duplication checks."
        ),
    )
    download_history: DirectoryPath = Field(
        default=_user_config_path / "download_history",
        title="Download history directory",
        description="Choose a root directory, where all download history objects are stored.",
    )
    selenium_driver_root: DirectoryPath = Field(
        default=_user_config_path / "selenium_drivers",
        title="Selenium webdriver directory",
        description=(
            "Choose a root directory, where all chromedriver and geckodriver binaries are stored.\n"
            "These binaries are required for easily adding things-to-download to your configuration."
        ),
    )
