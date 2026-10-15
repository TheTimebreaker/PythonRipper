import asyncio

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.subscription_management as sm
from pythonripper import __icon__
from pythonripper.toolbox.config import config


async def main() -> None:
    app = QApplication.instance() or QApplication([])
    if not isinstance(app, QApplication):
        raise
    if __icon__ and __icon__.is_file():
        app.setWindowIcon(QIcon(str(__icon__)))

    dialog = QDialog()
    dialog.setWindowTitle("Add New Entry")
    layout = QVBoxLayout(dialog)

    layout.addWidget(QLabel("Search the new entries for:"))
    entry_type = QComboBox()
    entry_type.addItem("Artists", "artist")
    entry_type.addItem("Tags", "tag")
    layout.addWidget(entry_type)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    obj: sm.CombinedFile
    if entry_type.currentData() == "artist":
        obj = sm.combined_artist_file
    else:
        obj = sm.combined_tags_file

    await add_entry_to_object(obj)


async def add_entry_to_object(obj: sm.CombinedFile) -> None:
    await obj.add_tags()


if __name__ == "__main__":
    cf.init_logger(config, "critical", False)
    asyncio.run(main())
