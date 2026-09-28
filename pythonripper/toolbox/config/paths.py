from pathlib import Path

import platformdirs

from pythonripper.toolbox.config import get_settings_object
from pythonripper.toolbox.config.model import AppSettings

_settings: AppSettings = get_settings_object()


class Paths:
    """Class for configuration elements loaded from the config file on-disk"""

    user_config_path = platformdirs.PlatformDirs("PythonRipper", "TheTimebreaker").user_config_path

    def _config(self) -> Path:
        return self.user_config_path / "config"

    def _config_json(self) -> Path:
        return self._config() / "config.json"

    def _credentials(self) -> Path:
        return self._config() / "credentials"

    def patreon_membership_status_json(self) -> Path:
        return self._config() / "patreon_memberships.json"

    def errorpath(self) -> Path:
        return self._config() / "!errors.log"

    def linkspath(self) -> Path:
        return self._config() / "!ripped_links.log"

    def blacklist_tags_path(self) -> Path:
        return self._config() / "blacklist_tags.txt"  # TODO(TheTimebreaker): PUT INTO CONFIG

    def artists_tags_path(self) -> Path:
        return self._config() / "artists.json"

    def booru_tags_path(self) -> Path:
        return self._config() / "booru_tags.json"

    def deviantart_favs_path(self) -> Path:
        return self._config() / "deviantart_favorites.txt"

    def newgrounds_favs_path(self) -> Path:
        return self._config() / "newgrounds_favorites.txt"

    def reddit_subs_path(self) -> Path:
        return self._config() / "reddit_subs.txt"

    def reddit_subsmonthly_path(self) -> Path:
        return self._config() / "reddit_subs_monthly.txt"

    def update_scheduler_json_path(self) -> Path:
        return self._config() / "update_scheduler.json"

    def process_downloads_log(self) -> Path:
        return self._config() / "process_downloads.log"

    def test_dir(self) -> Path:
        return self.user_config_path / "_test"

    def downloads(self) -> Path:
        p: Path = _settings.general.paths.downloads
        return p

    def storage(self) -> Path:
        p: Path = _settings.general.paths.storage
        return p

    def done_path(self) -> Path:
        p: Path = _settings.general.paths.archive
        return p

    def downloads_temp(self) -> Path:
        dl = self.downloads()
        return dl.with_name(dl.name + "-temp")

    def downloadhistory(self) -> Path:
        p: Path = _settings.general.paths.download_history
        return p

    def __selenium_driver(self) -> Path:
        p: Path = _settings.general.paths.selenium_driver_root
        return p

    def chromedriver_path(self) -> Path:  # TODO(TheTimebreaker): add geckodriver support AND setting for it
        return self.__selenium_driver() / "chromedriver_binaries"

    def geckodriver_path(self) -> Path:
        return self.__selenium_driver() / "geckodriver_binaries"


_paths = Paths()


class _Config:
    paths: Paths = _paths
    settings: AppSettings = _settings


config = _Config()
