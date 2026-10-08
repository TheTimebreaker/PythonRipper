import asyncio

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.subscription_management as sm
from pythonripper import __icon__
from pythonripper.toolbox.config import config


def create_divider() -> QFrame:
    divider = QFrame()
    divider.setFrameShape(QFrame.Shape.HLine)
    divider.setFrameShadow(QFrame.Shadow.Sunken)
    return divider


async def main() -> None:
    app = QApplication.instance() or QApplication([])
    if not isinstance(app, QApplication):
        raise
    if __icon__ and __icon__.is_file():
        app.setWindowIcon(QIcon(str(__icon__)))

    dialog = QDialog()
    dialog.setWindowTitle("Add New Website")
    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel("Search the new website's entries for:"))
    entry_type = QComboBox()
    entry_type.addItem("Artists", "artist")
    entry_type.addItem("Tags", "tag")
    layout.addWidget(entry_type)

    layout.addWidget(create_divider())

    layout.addWidget(QLabel("Choose the website to add:"))
    website = QComboBox()
    website.addItems(sm.combined_artist_file.websites)
    layout.addWidget(website)

    layout.addWidget(create_divider())

    layout.addWidget(QLabel("Automatically skip an entry if no existing tags can be found for any website:"))
    skip_empty_checkbox = QCheckBox("Enable auto-skip")
    layout.addWidget(skip_empty_checkbox)

    layout.addWidget(create_divider())

    layout.addWidget(QLabel("Check existing entries for more possible entries using aliases from other websites:"))
    check_existing_checkbox = QCheckBox("Check again")
    layout.addWidget(check_existing_checkbox)

    layout.addWidget(create_divider())

    layout.addWidget(QLabel("Skip processing the first <your value> number of elements:"))
    starting_index_spinbox = QSpinBox(maximum=2**16)
    layout.addWidget(starting_index_spinbox)

    layout.addWidget(create_divider())

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if not sm.combined_artist_file.websites or not sm.combined_tags_file.websites:
        website.setEnabled(False)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    obj: sm.CombinedFile
    if entry_type.currentData() == "artist":
        obj = sm.combined_artist_file
        func = add_artists
    else:
        obj = sm.combined_tags_file
        func = add_tag

    website_choice = website.currentText()
    skip_empty = skip_empty_checkbox.isChecked()
    check_existing_again = check_existing_checkbox.isChecked()
    starting_index: int = starting_index_spinbox.value()
    await func(obj, website_choice, skip_empty, check_existing_again, starting_index)


async def add_artists(obj: sm.CombinedFile, choice: str, skip_empty: bool, check_existing_again: bool, starting_index: int) -> None:
    await obj.add_website(choice, skip_empty, check_existing_again, starting_index)


async def add_tag(obj: sm.CombinedFile, choice: str, skip_empty: bool, check_existing_again: bool, starting_index: int) -> None:
    await obj.add_website(choice, skip_empty, check_existing_again, starting_index)


if __name__ == "__main__":
    cf.init_logger(config, "critical", False)
    asyncio.run(main())
