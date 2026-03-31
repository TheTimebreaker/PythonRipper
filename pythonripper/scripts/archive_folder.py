from pathlib import Path
from tkinter.filedialog import askdirectory

from duplicate_image_finder import hashfiles


def main() -> None:
    directory = Path(askdirectory())
    print(directory)

    archive = hashfiles.ArchiveHashfile(directory)
    archive.archive_folder(delete_source=False)


if __name__ == "__main__":
    main()
