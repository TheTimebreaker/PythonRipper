import logging
import random
import shutil
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
from pythonripper import __icon__


def main() -> None:
    # Enter arguments
    selected_directory = QFileDialog.getExistingDirectory(None, "Select directory")
    if not selected_directory:
        return
    directory = Path(selected_directory)
    path = directory
    print(directory)

    number, ok = QInputDialog.getInt(
        None,
        "Collect random files",
        "Enter how many files you want to collect.",
        1,
        1,
        9999,
        1,
    )
    if not ok:
        return

    # Create file list
    print("Loading file list... ", end="")
    collected_files = []
    all_files = [file for file in f.list_files(path, include_subdirs=False) if "!hashes" not in file.stem]
    random.shuffle(all_files)
    print("Done!")

    # Collect files
    collected_files = all_files[0:number]

    # Move files to temp
    temppath = path / f"temp-{cf.id_generator(6)}"
    temppath.mkdir(parents=True, exist_ok=True)
    for i, file in enumerate(collected_files):
        cf.progress_bar(i + 1, number, "Moving files...")
        shutil.move(file, temppath)

    print("Done!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    app = QApplication.instance() or QApplication([])
    if not isinstance(app, QApplication):
        raise

    if __icon__ and __icon__.is_file():
        app.setWindowIcon(QIcon(str(__icon__)))

    main()
