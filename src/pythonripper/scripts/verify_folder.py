import asyncio
import logging
import re
import shutil
import traceback
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, TypedDict

import send2trash
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

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


def __process_file(file: Path, processing_option: ProcessingOptions) -> None:
    if processing_option == ProcessingOptions.SKIP:
        return
    elif processing_option == ProcessingOptions.DELETE:
        send2trash.send2trash(file)
    elif processing_option == ProcessingOptions.MOVE:
        target_dir = file.parent / "moved"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / file.name
        shutil.move(file, target)
    else:
        raise NotImplementedError("Unimplemented processing option set.")


async def _verify(
    directory: Path, settings: AppSettings, blacklisted_processing: ProcessingOptions, disallowed_rating_processing: ProcessingOptions
) -> None:
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
    blacklisted: int = 0
    content_ratings: int = 0

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
            __process_file(filepath, processing_option=blacklisted_processing)
            blacklisted += 1

        elif not issuer.is_content_rating_allowed(data):
            print(f"Content rating disallowed!: {filepath}")
            __process_file(filepath, processing_option=disallowed_rating_processing)
            content_ratings += 1

        else:
            print(f"All good: {filepath}")

    await asyncio.gather(*workers, return_exceptions=True)

    print("=" * 20)
    print(f"Finished verifying folder {directory}")
    print(f"Files processed: #{len(all_files)}")
    print(f"Blacklisted tags found in files: #{blacklisted}")
    print(f"Disallowed content ratings found in files: #{content_ratings}")


class ProcessingOptions(StrEnum):
    SKIP = "Skip matches"
    DELETE = "Delete matches"
    MOVE = "Move matches to a subdirectory"


class ProcessingWindow(QMainWindow):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Processing Options")
        self.resize(700, 300)

        self.selected_directory: Path | None = None
        self.blacklisted_tag_option: ProcessingOptions | None = None
        self.disallowed_rating_option: ProcessingOptions | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        text = (
            "This tool allows you to re-verify already downloaded files in regards to content ratings and blacklisted tags.\n"
            "May be useful, if your preferences have changed or for sorting downloaded files.\n"
            "Please choose from the settings below the to-be-verified directory and what you want to do with matches."
        )
        self.explainer_text = QLabel(text=text)
        layout.addWidget(self.explainer_text)

        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: palette(mid);")
        layout.addWidget(divider)

        directory_layout = QHBoxLayout()
        directory_layout.addWidget(QLabel("Directory:"))
        self.directory_field = QLineEdit()
        self.directory_field.setReadOnly(True)
        directory_layout.addWidget(self.directory_field)
        browse_button = QPushButton("Select...")
        browse_button.clicked.connect(self._select_directory)
        directory_layout.addWidget(browse_button)
        layout.addLayout(directory_layout)

        self.blacklisted_combo = self._create_option_selector(
            "Blacklisted tag found:",
            layout,
            default=ProcessingOptions.MOVE,
        )

        self.disallowed_rating_combo = self._create_option_selector(
            "Disallowed content rating:",
            layout,
            default=ProcessingOptions.MOVE,
        )

        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def _create_option_selector(
        self,
        label_text: str,
        parent_layout: QVBoxLayout,
        default: ProcessingOptions | None = None,
    ) -> QComboBox:
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))

        combo = QComboBox()
        for option in ProcessingOptions:
            combo.addItem(option.value, option)

        # Select the default enum value.
        if default is not None:
            index = combo.findData(default)
            if index >= 0:
                combo.setCurrentIndex(index)

        row.addWidget(combo, 1)
        parent_layout.addLayout(row)
        return combo

    def _select_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select directory",
        )
        if directory:
            self.selected_directory = Path(directory)
            self.directory_field.setText(directory)

    def accept(self) -> None:
        self.blacklisted_tag_option = self.blacklisted_combo.currentData()
        self.disallowed_rating_option = self.disallowed_rating_combo.currentData()

        # Require exactly one option for each selector.
        if any(value is None for value in (self.blacklisted_tag_option, self.disallowed_rating_option, self.selected_directory)):
            QMessageBox.warning(
                self,
                "Missing value",
                "Please select an option for every field.",
            )
            return

        self.close()

    def reject(self) -> None:
        QApplication.instance().quit()  # type: ignore


def main(app: QApplication) -> None:
    # General processing settings
    window = ProcessingWindow()
    window.show()
    app.exec()

    directory = window.selected_directory
    blacklisted_processing = window.blacklisted_tag_option
    disallowed_rating_processing = window.disallowed_rating_option

    if any(x is None for x in (directory, blacklisted_processing, disallowed_rating_processing)):
        return
    assert directory and blacklisted_processing and disallowed_rating_processing

    # Edit session settings
    dialog = QMessageBox(
        QMessageBox.Icon.Information,
        "Verify folder",
        (
            "If you confirm, a temporary settings window will appear where you can change the settings for this session.\n"
            "THESE SETTINGS WILL NOT BE PERMANENTLY SAVED AND DO NOT AFFECT YOUR APPLICATION SETTINGS!\n\n"
            "Also, keep in mind that this is a copy of the entire config, so there will be many option that don't do anything here."
        ),
    )
    dialog.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
    cancel_button = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    dialog.setDefaultButton(cancel_button)
    dialog.exec()
    if dialog.clickedButton() == cancel_button:
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

    asyncio.run(
        _verify(
            directory,
            temp_settings,
            blacklisted_processing=blacklisted_processing,
            disallowed_rating_processing=disallowed_rating_processing,
        )
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    app = QApplication.instance() or QApplication([])
    if not isinstance(app, QApplication):
        raise

    if __icon__ and __icon__.is_file():
        app.setWindowIcon(QIcon(str(__icon__)))

    main(app)
