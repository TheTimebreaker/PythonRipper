import asyncio
import sys
from enum import StrEnum
from pathlib import Path

from pydantic_gui_settings_editor import Theme
from PySide6.QtGui import QIcon, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

from pythonripper import __version__
from pythonripper.scripts import update_scheduler
from pythonripper.toolbox.config import config, get_settingsmanager_object


class Choices(StrEnum):
    UPDATE_SCHEDULER = "update-scheduler"
    SETTINGS = "settings"
    MISC = "misc"


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication, icon: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"PythonRipper {__version__}")
        if icon and icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))

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
        for label, callback in (
            ("Run update", lambda: self.apply_choice(Choices.UPDATE_SCHEDULER)),
            ("Open config", lambda: self.apply_choice(Choices.SETTINGS)),
            ("Misc", lambda: self.apply_choice(Choices.MISC)),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            layout.addWidget(button)
        self.setCentralWidget(buttons)

    def apply_choice(self, choice: Choices) -> None:
        self.choice = choice
        self.close()


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    icon = root / "img" / "icon.jpg"

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
            asyncio.run(update_scheduler.update_all(config))
        case Choices.SETTINGS:
            manager = get_settingsmanager_object()
            manager.edit_gui()
        case Choices.MISC:
            print("not implemented")
        case _:
            print("No valid choice made. Exiting...")


if __name__ == "__main__":
    main()
