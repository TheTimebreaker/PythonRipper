import asyncio
import sys
from enum import StrEnum
from pathlib import Path

from pydantic_gui_settings_editor import Theme
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QIcon, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pythonripper import __icon__, __version__
from pythonripper.scripts import (
    add_new_entry,
    add_new_website,
    archive_folder,
    pack_random_files,
    process_downloads,
    update_scheduler,
    verify_folder,
    verify_tagfiles,
)
from pythonripper.toolbox.config import config, get_settingsmanager_object


class Choices(StrEnum):
    UPDATE_SCHEDULER = "update-scheduler"
    SETTINGS = "settings"
    MISC = "misc"


class MiscScripts(StrEnum):
    ADD_ENTRY = "add_entry"
    ADD_WEBSITE = "add_website"
    ARCHIVE_FOLDER = "add_folder"
    PACK_RANDOM_FILES = "pack_random_files"
    PROCESS_DOWNLOADS = "process_downloads"
    VERIFY_TAGFILES = "verify_tagfiles"
    VERIFY_FOLDER = "verify_folder"


class MiscWindow(QMainWindow):
    def __init__(self, app: QApplication, icon: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"PythonRipper {__version__} / Misc")
        self.icon = icon
        if self.icon and self.icon.is_file():
            self.setWindowIcon(QIcon(str(self.icon)))

        theme = config.settings.general.theme
        if theme is Theme.LIGHT:
            app.styleHints().setColorScheme(Qt.ColorScheme.Light)
        elif theme is Theme.DARK:
            app.styleHints().setColorScheme(Qt.ColorScheme.Dark)

        self.choice: MiscScripts | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        buttons = QWidget(self)
        layout = QVBoxLayout(buttons)

        label1 = QLabel("Miscellaneous tasks")
        font = label1.font()
        font.setPointSize(24)
        label1.setFont(font)
        layout.addWidget(label1)
        for label, callback, tooltip in (
            (
                "Add new entry",
                lambda: self.apply_choice(MiscScripts.ADD_ENTRY),
                "Opens the subprogram for adding new artists/tags to your subscribed lists.",
            ),
            (
                "Add new website",
                lambda: self.apply_choice(MiscScripts.ADD_WEBSITE),
                "Opens the subprogram for adding a new website to your subscribed lists based on your other websites' lists.",
            ),
            (
                "Archive folder",
                lambda: self.apply_choice(MiscScripts.ARCHIVE_FOLDER),
                (
                    "Choose a folder to turn into a hash archive. This will allow these files to be used for future duplication checks,\n"
                    "but without keeping the file. Useful for saving disk space."
                ),
            ),
            (
                "Pack random files",
                lambda: self.apply_choice(MiscScripts.PACK_RANDOM_FILES),
                "Choose a folder and a number. Will choose <number> random items from that folder and move them into a temp subdirectory.",
            ),
            (
                "Process downloads",
                lambda: self.apply_choice(MiscScripts.PROCESS_DOWNLOADS),
                (
                    "Run the download processor. Moves files from 'downloads' to 'storage' (set in settings).\n"
                    "Removes unwanted files. Converts image files to desired output format. Merges folders from the same tag.\n"
                    "Checks file name length. Check for duplicate files."
                ),
            ),
            (
                "Verify tagfiles",
                lambda: self.apply_choice(MiscScripts.VERIFY_TAGFILES),
                "Initiates the artist and tag tagfiles, which will print all issues to the console.",
            ),
            (
                "Verify folder",
                lambda: self.apply_choice(MiscScripts.VERIFY_FOLDER),
                "Allows you to re-verify the files in a folder based on your current preferences.",
            ),
        ):
            button = QPushButton(label)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            layout.addWidget(button)
        self.setCentralWidget(buttons)

    def apply_choice(self, choice: MiscScripts) -> None:
        self.choice = choice
        self.close()


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication, icon: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"PythonRipper {__version__}")
        self.icon = icon
        if self.icon and self.icon.is_file():
            self.setWindowIcon(QIcon(str(self.icon)))

        theme = config.settings.general.theme
        if theme is Theme.LIGHT:
            app.styleHints().setColorScheme(Qt.ColorScheme.Light)
        elif theme is Theme.DARK:
            app.styleHints().setColorScheme(Qt.ColorScheme.Dark)

        self.choice: Choices | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        buttons = QWidget(self)
        layout = QVBoxLayout(buttons)

        label1 = QLabel(f"PythonRipper {__version__}")
        font = label1.font()
        font.setPointSize(24)
        label1.setFont(font)
        layout.addWidget(label1)

        for label, callback, tooltip in (
            (
                "Run update",
                lambda: self.apply_choice(Choices.UPDATE_SCHEDULER),
                "Run the scheduler to update all subscribed artists and tags.",
            ),
            (
                "Open config",
                lambda: self.apply_choice(Choices.SETTINGS),
                "Open the application settings editor to configure PythonRipper.",
            ),
            (
                "Misc",
                lambda: self.apply_choice(Choices.MISC),
                "Open the miscellaneous tools menu for extra utilities and maintenance tasks.",
            ),
        ):
            button = QPushButton(label)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            layout.addWidget(button)
        self.setCentralWidget(buttons)
        self.menuBar().addAction("About", self.show_about)

    def show_about(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("About PythonRipper")
        layout = QVBoxLayout(dialog)

        label1 = QLabel(f"PythonRipper {__version__}")
        font = label1.font()
        font.setPointSize(24)
        label1.setFont(font)
        title_widget = QWidget(dialog)
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 10, 0, 10)
        title_layout.setSpacing(8)
        if self.icon and self.icon.is_file():
            icon_label = QLabel(
                pixmap=QIcon(str(self.icon)).pixmap(label1.sizeHint().height(), label1.sizeHint().height()),
            )
            icon_label.setFixedSize(label1.sizeHint().height(), label1.sizeHint().height())
            title_layout.addWidget(icon_label)
        title_layout.addWidget(label1)
        layout.addWidget(title_widget)

        layout.addWidget(QFrame(frameShadow=QFrame.Shadow.Sunken, frameShape=QFrame.Shape.HLine))

        layout.addWidget(QLabel("A tool for downloading and updating local copies of subscribed artists and tags across many differen websites."))
        profile_url = "https://github.com/TheTimebreaker"
        link_profile = QLabel(f'Written mostly in Python / Qt by <a href="{profile_url}">TheTimebreaker</a>.')
        link_profile.setOpenExternalLinks(False)
        link_profile.linkActivated.connect(lambda profile_url: QDesktopServices.openUrl(QUrl(profile_url)))
        layout.addWidget(link_profile)

        layout.addWidget(QFrame(frameShadow=QFrame.Shadow.Sunken, frameShape=QFrame.Shape.HLine))

        repository_url = "https://github.com/TheTimebreaker/PythonRipper"
        repository_link_label = QLabel(f'<a href="{repository_url}">GitHub repository</a>')
        repository_link_label.setOpenExternalLinks(False)
        repository_link_label.linkActivated.connect(lambda repository_url: QDesktopServices.openUrl(QUrl(repository_url)))
        layout.addWidget(repository_link_label)

        issues_url = "https://github.com/TheTimebreaker/PythonRipper"
        issues_link_label = QLabel(f'<a href="{issues_url}">Submit an issue or a feature request</a>')
        issues_link_label.setOpenExternalLinks(False)
        issues_link_label.linkActivated.connect(lambda issues_url: QDesktopServices.openUrl(QUrl(issues_url)))
        layout.addWidget(issues_link_label)
        dialog.exec()

    def apply_choice(self, choice: Choices) -> None:
        self.choice = choice
        self.close()


async def main() -> None:
    icon = __icon__
    # Main window
    app = QApplication.instance() or QApplication(sys.argv)
    if not isinstance(app, QApplication):
        raise

    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow(app, icon=icon)
    window.show()
    app.exec()

    print("Chosen script:")
    print(window.choice)
    print("=" * 20)

    match window.choice:
        case Choices.UPDATE_SCHEDULER:
            await update_scheduler.update_all(config)
            return
        case Choices.SETTINGS:
            manager = get_settingsmanager_object()
            manager.edit_gui()
            return
        case Choices.MISC:
            pass
        case _:
            print("No valid choice made. Exiting...")
            return

    # MISC
    window2 = MiscWindow(app, icon=icon)
    window2.show()
    app.exec()

    print("Chosen misc script:")
    print(window2.choice)
    print("=" * 20)

    match window2.choice:
        case MiscScripts.ADD_ENTRY:
            await add_new_entry.main()
        case MiscScripts.ADD_WEBSITE:
            await add_new_website.main()
        case MiscScripts.ARCHIVE_FOLDER:
            archive_folder.main(app)
        case MiscScripts.PACK_RANDOM_FILES:
            pack_random_files.main()
        case MiscScripts.PROCESS_DOWNLOADS:
            await process_downloads.main()
        case MiscScripts.VERIFY_TAGFILES:
            await verify_tagfiles.main()
        case MiscScripts.VERIFY_FOLDER:
            await verify_folder.main()
        case _:
            print("No valid choice made. Exiting...")


if __name__ == "__main__":
    asyncio.run(main())
