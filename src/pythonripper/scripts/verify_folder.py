import asyncio
import re
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile, mkstemp
from typing import Coroutine, Literal, TypedDict

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scrap
from pythonripper import __icon__
from pythonripper.extractor.artstation import ArtstationAPI
from pythonripper.extractor.danbooru import DanbooruAPI
from pythonripper.extractor.deviantart import DeviantartAPI
from pythonripper.extractor.gelbooru import GelbooruAPI
from pythonripper.extractor.hentaifoundry import HentaiFoundryArtist
from pythonripper.extractor.hypnohub import HypnohubAPI
from pythonripper.extractor.kusowanka import KusowankaAPI
from pythonripper.extractor.newgrounds import NewgroundsAPI
from pythonripper.extractor.pixiv import PixivArtistAPI
from pythonripper.extractor.rule34paheal import Rule34pahealAPI
from pythonripper.extractor.rule34us import Rule34usAPI
from pythonripper.extractor.rule34xxx import Rule34xxxAPI
from pythonripper.extractor.tumblr import TumblrAPI
from pythonripper.extractor.yandere import YandereAPI
from pythonripper.toolbox.config import AppSettings, config, get_settingsmanager_object


class WorkerResult(TypedDict):
    path: Path


async def _worker(queue: asyncio.Queue[str], obj: type[scrap.Scraper], settings: AppSettings, files: list[Path]) -> None:
    obj_active = obj(config)
    await obj_active.init()
    if not hasattr(obj_active, "FILENAME_TO_ID_PATTERN"):
        print(f"{obj_active.ME} has not filename to ID pattern")
    pattern = obj.FILENAME_TO_ID_PATTERN
    for file in files:
        identifier = re.match(pattern, file.name)
        print(obj_active.ME, identifier)
        # await obj_active._get_post_data()
        timeout = random.randint(100, 2000)
        await asyncio.sleep(timeout / 1000)
        await queue.put(str(file))
    await queue.put(None)
    return


async def _verify(directory: Path, settings: AppSettings, delete_files: bool) -> None:
    # Create file list
    print("Loading file list... ", end="")
    all_files = [file for file in f.list_files(directory, include_subdirs=False) if "!hashes" not in file.stem]
    print("Done!")

    # ignored services:
    # all artist websites: usually no tagging, also you specifically chose this artist
    # Patreon: no tagging whatsoever. also, you likely paid for this, so take the files
    objects_by_module: dict[str, type[scrap.Scraper]] = {
        "artstation": ArtstationAPI,
        "danbooru": DanbooruAPI,
        "deviantart": DeviantartAPI,
        "gelbooru": GelbooruAPI,
        # "hentaifoundry": HentaiFoundryArtist,  # noqa: ERA001 # Will be implemented later
        "hypnohub": HypnohubAPI,
        "kusowanka": KusowankaAPI,
        "newgrounds": NewgroundsAPI,
        "pixiv": PixivArtistAPI,
        "rule34paheal": Rule34pahealAPI,
        "rule34us": Rule34usAPI,
        "rule34xxx": Rule34xxxAPI,
        "tumblr": TumblrAPI,
        "yandere": YandereAPI,
    }
    files_by_module: dict[str, list[Path]] = {service: [] for service in objects_by_module}
    for file in all_files:
        for module in objects_by_module:
            if file.name.startswith(module):
                files_by_module[module].append(file)
                break

    queue: asyncio.Queue[str] = asyncio.Queue()
    workers = [asyncio.create_task(_worker(queue, obj, settings, files_by_module[module])) for module, obj in objects_by_module.items()]
    finished: int = 0

    while finished < len(workers):
        result = await queue.get()

        if result is None:
            finished += 1
            continue

        # Consume the result immediately.
        print(f"{result}")

    await asyncio.gather(*workers)

    print("yeet")


def main() -> None:
    selected_directory = QFileDialog.getExistingDirectory(None, "Select directory")
    if not selected_directory:
        return
    directory = Path(selected_directory)
    print(directory)

    dialog = QMessageBox(
        QMessageBox.Icon.Information,
        "Verify folder",
        (
            "If you confirm, a temporary settings window will appear where you can change the settings for this session.\n"
            "THESE SETTINGS WILL NOT BE PERMANENTLY SAVED AND DO NOT AFFECT YOUR APPLICATION SETTINGS!\n"
            "After that, the temporary settings will be compared against the files in the selected directory.\n"
            "Specifically, the files will be checked against the blacklist and against content filters IGNORING BYPASS SETTINGS.\n"
            "Files, that fail to meet these criteria, can either be deleted or moved to another folder."
            f"Continue with processing {directory}?"
        ),
    )
    delete_button = dialog.addButton("Continue, delete files", QMessageBox.ButtonRole.AcceptRole)
    move_button = dialog.addButton("Continue, move files", QMessageBox.ButtonRole.AcceptRole)
    cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    dialog.setDefaultButton(cancel_button)
    dialog.exec()
    delete_or_move: Literal["delete", "move"]
    if dialog.clickedButton() == delete_button:
        delete_or_move = "delete"
    elif dialog.clickedButton() == move_button:
        delete_or_move = "move"
    else:
        return

    tmp_dir = NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, prefix="config", suffix=".json")
    tmp_dir.write(config.settings.model_dump_json())
    tmp_dir.close()
    tmp_path = Path(tmp_dir.name)
    try:
        manager = get_settingsmanager_object(tmp_path)
        manager.load()
        manager.edit_gui()

        temp_settings = manager.model.model_copy(deep=True)

    finally:
        tmp_dir.close()
        tmp_path.unlink(missing_ok=True)

    asyncio.run(_verify(directory, temp_settings, delete_files=bool(delete_or_move == "delete")))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # app = QApplication.instance() or QApplication([])
    # if not isinstance(app, QApplication):
    #     raise

    # if __icon__ and __icon__.is_file():
    #     app.setWindowIcon(QIcon(str(__icon__)))

    # main()

    p = Path(r"D:\AppData\TheTimebreaker\PythonRipper\files\archive\booru\sybian - Copy")
    asyncio.run(_verify(p, config.settings.model_copy(deep=True), False))
