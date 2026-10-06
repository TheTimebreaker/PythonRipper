import asyncio
import logging
import re
import shutil
import traceback
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal, TypedDict

import send2trash
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper import __icon__
from pythonripper.extractor.artstation import ArtstationAPI
from pythonripper.extractor.danbooru import DanbooruAPI
from pythonripper.extractor.deviantart import DeviantartAPI
from pythonripper.extractor.gelbooru import GelbooruAPI
from pythonripper.extractor.hypnohub import HypnohubAPI
from pythonripper.extractor.kusowanka import KusowankaAPI
from pythonripper.extractor.pixiv import PixivArtistAPI
from pythonripper.extractor.rule34paheal import Rule34pahealAPI
from pythonripper.extractor.rule34us import Rule34usAPI
from pythonripper.extractor.rule34xxx import Rule34xxxAPI
from pythonripper.extractor.yandere import YandereAPI
from pythonripper.toolbox.config import AppSettings, ConfigObject, config, get_settingsmanager_object


class WorkerResult(TypedDict):
    issuer: scraper.Scraper
    path: Path
    data: scraper.PostData


async def _worker(queue: asyncio.Queue[WorkerResult | None], obj: type[scraper.Scraper], config: ConfigObject, files: list[Path]) -> None:
    try:
        obj_active = obj(config)
        await obj_active.init()
        if not hasattr(obj_active, "FILENAME_TO_ID_PATTERN"):
            print(f"{obj_active.ME} has not filename to ID pattern")
        pattern = obj.FILENAME_TO_ID_PATTERN
        for file in files:
            identifier = re.match(pattern, file.name)
            assert identifier

            # accouting for username+ID vs ID
            username = None
            try:
                ide = identifier.group(2)
                username = identifier.group(1)
                args = {"post_id": ide, "tagname": username}
            except IndexError:
                ide = identifier.group(1)
                args = {"post_id": ide}

            try:
                post_data = await obj_active._get_post_data(**args)  # type: ignore
            except cf.ExtractorSkipError, cf.ExtractorExitError:
                continue

            result = WorkerResult(
                issuer=obj_active,
                path=file,
                data=post_data,
            )
            await queue.put(result)

    except Exception as e:
        print(f"Worker crashed: {type(e).__name__}: {e}")
        traceback.print_exc()

    finally:  # ALWAYS signals that this worker is done
        await queue.put(None)


def __process_file(file: Path, delete_files: bool) -> None:
    if delete_files:
        send2trash.send2trash(file)
    else:
        target_dir = file.parent / "removed"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / file.name
        shutil.move(file, target)


async def _verify(directory: Path, settings: AppSettings, delete_files: bool) -> None:
    # Create file list
    print("Loading file list... ", end="")
    all_files = [file for file in f.list_files(directory, include_subdirs=False) if "!hashes" not in file.stem]
    print("Done!")

    # ignored services:
    # all artist websites: usually no tagging, also you specifically chose this artist
    # Newgrounds: no good ID retrival
    # Hentaifoundry: no tags retrieved
    # TumblrAPI: no tags
    # Patreon: no tagging whatsoever. also, you likely paid for this, so take the files
    objects_by_module: dict[str, type[scraper.Scraper]] = {
        "artstation": ArtstationAPI,
        "danbooru": DanbooruAPI,
        "deviantart": DeviantartAPI,
        "gelbooru": GelbooruAPI,
        "hypnohub": HypnohubAPI,
        "kusowanka": KusowankaAPI,
        "pixiv": PixivArtistAPI,
        "rule34paheal": Rule34pahealAPI,
        "rule34us": Rule34usAPI,
        "rule34xxx": Rule34xxxAPI,
        "yandere": YandereAPI,
    }
    files_by_module: dict[str, list[Path]] = {service: [] for service in objects_by_module}
    for file in all_files:
        for module in objects_by_module:
            if file.name.startswith(module):
                files_by_module[module].append(file)
                break

    queue: asyncio.Queue[WorkerResult | None] = asyncio.Queue()
    config = ConfigObject()
    config.settings = settings
    workers = [asyncio.create_task(_worker(queue, obj, config, files_by_module[module])) for module, obj in objects_by_module.items()]
    finished: int = 0

    while finished < len(workers):
        result = await queue.get()
        if result is None:
            finished += 1
            continue

        issuer = result["issuer"]
        data = result["data"]
        filepath = result["path"]

        if issuer.blacklist_tag_found(data):
            print(f"Blacklisted!: {filepath}")
            __process_file(filepath, delete_files=delete_files)

        elif not issuer.is_content_rating_allowed(data):
            print(f"Content rating disallowed!: {filepath}")
            __process_file(filepath, delete_files=delete_files)

        else:
            print(f"All good: {filepath}")

    await asyncio.gather(*workers, return_exceptions=True)


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

    app = QApplication.instance() or QApplication([])
    if not isinstance(app, QApplication):
        raise

    if __icon__ and __icon__.is_file():
        app.setWindowIcon(QIcon(str(__icon__)))

    main()

    p = Path(r"D:\AppData\TheTimebreaker\PythonRipper\files\archive\booru\rope bondage")
    asyncio.run(_verify(p, config.settings.model_copy(deep=True), False))
