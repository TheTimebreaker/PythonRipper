import logging
from pathlib import Path

from duplicate_image_finder import hashfiles
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from pythonripper import __icon__


def main(_app: QApplication) -> None:

    selected_directory = QFileDialog.getExistingDirectory(None, "Select directory")
    if not selected_directory:
        return
    directory = Path(selected_directory)
    print(directory)

    answer = QMessageBox.question(
        None,
        "Delete source files?",
        "Delete the source files after the archive is created?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    if answer == QMessageBox.StandardButton.Cancel:
        return
    delete_source = answer == QMessageBox.StandardButton.Yes

    print(f"Archiving folder {directory}")
    logging.info("test")
    print(f"Deleting files after processing: {delete_source}")
    archive = hashfiles.ArchiveHashfile(directory)
    archive.archive_folder(delete_source=delete_source)
    print("Finished!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    app = QApplication.instance() or QApplication([])
    if not isinstance(app, QApplication):
        raise

    if __icon__ and __icon__.is_file():
        app.setWindowIcon(QIcon(str(__icon__)))

    main(app)
