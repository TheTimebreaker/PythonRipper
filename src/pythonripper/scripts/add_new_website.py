import asyncio

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QListWidget,
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
    entry_type.addItem("Favorites", "favorites")
    entry_type.addItem("Tags", "tag")
    layout.addWidget(entry_type)

    layout.addWidget(create_divider())

    layout.addWidget(QLabel("Choose the website to add:"))
    website = QListWidget()
    website.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
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

    layout.addWidget(QLabel("Only allow new entries, if they have atleast one post:"))
    must_have_posts_checkbox = QCheckBox("Must have posts")
    layout.addWidget(must_have_posts_checkbox)

    layout.addWidget(create_divider())

    layout.addWidget(QLabel("Skip processing the first <your value> number of elements:"))
    starting_index_spinbox = QSpinBox(maximum=2**16)
    layout.addWidget(starting_index_spinbox)

    layout.addWidget(create_divider())

    layout.addWidget(QLabel("Add tab-opening delay (in ms):"))
    delay_ms_spinbox = QSpinBox(maximum=5000)
    layout.addWidget(delay_ms_spinbox)

    layout.addWidget(create_divider())

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)

    def update_websites() -> None:
        websites = (
            sm.combined_artist_file.websites
            if entry_type.currentData() == "artist"
            else sm.combined_favorites_file.websites if entry_type.currentData() == "favorites" else sm.combined_tags_file.websites
        )
        selected_websites = {item.text() for item in website.selectedItems()}
        website.clear()
        website.addItems(websites)
        for index in range(website.count()):
            item = website.item(index)
            if item.text() in selected_websites:
                item.setSelected(True)
        website.setEnabled(bool(websites))
        ok_button.setEnabled(bool(website.selectedItems()))

    website.itemSelectionChanged.connect(lambda: ok_button.setEnabled(bool(website.selectedItems())))
    update_websites()
    entry_type.currentIndexChanged.connect(update_websites)

    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    obj: sm.CombinedFile
    if entry_type.currentData() == "artist":
        obj = sm.combined_artist_file
    elif entry_type.currentData() == "favorites":
        obj = sm.combined_favorites_file
    else:
        obj = sm.combined_tags_file

    website_choices = [item.text() for item in website.selectedItems()]
    skip_empty = skip_empty_checkbox.isChecked()
    check_existing_again = check_existing_checkbox.isChecked()
    must_have_posts = must_have_posts_checkbox.isChecked()
    starting_index: int = starting_index_spinbox.value()
    tab_opening_delay_ms: int = delay_ms_spinbox.value()
    await add_website_to_object(obj, website_choices, skip_empty, check_existing_again, must_have_posts, starting_index, tab_opening_delay_ms)


async def add_website_to_object(
    obj: sm.CombinedFile,
    choice: list[str] | str,
    skip_empty: bool,
    check_existing_again: bool,
    must_have_posts: bool,
    starting_index: int,
    tab_opening_delay_ms: int,
) -> None:
    await obj.add_website(choice, skip_empty, check_existing_again, must_have_posts, starting_index, tab_opening_delay_ms)


if __name__ == "__main__":
    cf.init_logger(config, "critical", False)
    asyncio.run(main())
