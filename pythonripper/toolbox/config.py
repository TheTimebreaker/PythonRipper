"""Provides the central Config class, which should be used whereever configuration things are needed."""

import json
import os
import shutil
from pathlib import Path

import platformdirs

user_config_dir = platformdirs.PlatformDirs("PythonRipper", "TheTimebreaker").user_config_path

# This sets the default values for the config dirs to make things run smoothly in DOCKER and on host OS
os.environ.setdefault("DOWNLOAD_DIR", str(user_config_dir / "!Downloaded stuff"))
os.environ.setdefault("CONFIG_DIR", str(user_config_dir / "config"))
os.environ.setdefault("DOWNLOADHISTORY_DIR", str(user_config_dir / "download_history"))
os.environ.setdefault("CHROMEDRIVER_DIR", str(Path(r"D:\Documents\Visual Studio Code projects\_chromedriver")))


class Config:
    """Class for configuration elements loaded from config.json"""

    def __init__(self) -> None:
        self.path = self._config_path() / "config.json"
        try:
            with open(self.path, encoding="utf-8") as file:
                self.data = json.load(file)
        except FileNotFoundError as error:
            for file_suffix in (".bak", ".tmp"):
                suffix_path = self.path.with_name(self.path.name + file_suffix)
                if suffix_path.is_file():
                    with open(suffix_path, encoding="utf-8") as file:
                        self.data = json.load(file)
                    shutil.copy(suffix_path, self.path)
                    return
            raise FileExistsError("None of the fallback files found.") from error

    def _downloaded_path(self) -> Path:
        val = os.environ.get("DOWNLOAD_DIR")
        if val is None:
            raise ValueError
        return Path(val)

    def _config_path(self) -> Path:
        val = os.environ.get("CONFIG_DIR")
        if val is None:
            raise ValueError
        return Path(val)

    def _downloadhistory_path(self) -> Path:
        val = os.environ.get("DOWNLOADHISTORY_DIR")
        if val is None:
            raise ValueError
        return Path(val)

    def test_dir(self) -> Path:
        return self._downloaded_path() / "test"

    def _credentials_path(self) -> Path:
        return self._config_path() / "credentials"

    def patreon_membership_status_json(self) -> Path:
        return self._config_path() / "patreon_memberships.json"

    def dpath(self) -> Path:
        return self._downloaded_path() / "B-download"

    def dpath_tmp(self) -> Path:
        return self.dpath().with_name(self.dpath().name + "-temp")

    def _processedfiles_path(self) -> Path:
        return self._downloaded_path() / "A-Sorted and dupechecked"

    def done_path(self) -> Path:
        return self._processedfiles_path() / "!DONE"

    def notdone_path(self) -> Path:
        return self._processedfiles_path() / "Notdone"

    def errorpath(self) -> Path:
        return self._config_path() / "!errors.log"

    def linkspath(self) -> Path:
        return self._config_path() / "!ripped-links.log"

    def blacklist_tags_path(self) -> Path:
        return self._config_path() / "blacklist_tags.txt"

    def artists_tags_path(self) -> Path:
        return self._config_path() / "artists.json"

    def booru_tags_path(self) -> Path:
        return self._config_path() / "booru_tags.json"

    def deviantart_favs_path(self) -> Path:
        return self._config_path() / "deviantart favorites.txt"

    def newgrounds_favs_path(self) -> Path:
        return self._config_path() / "newgrounds favorites.txt"

    def reddit_subs_path(self) -> Path:
        return self._config_path() / "reddit subs.txt"

    def reddit_subsmonthly_path(self) -> Path:
        return self._config_path() / "reddit subs monthly.txt"

    def update_scheduler_json_path(self) -> Path:
        return self._config_path() / "update_scheduler.json"

    def process_downloads_log(self) -> Path:
        return self._config_path() / "process_downloads.log"

    def chromedriver_path(self) -> Path:
        val = os.environ.get("CHROMEDRIVER_DIR")
        if val is None:
            raise ValueError
        return Path(val)

    async def write_config(self) -> None:
        import pythonripper.toolbox.files as f

        content = json.dumps(self.data, indent=4, sort_keys=True)
        await f.atomic_write(self.path, content)


c = Config()
print(c._downloadhistory_path())
