import datetime
import random
import shutil
from pathlib import Path
from tkinter.filedialog import askdirectory

from easygui import integerbox

import toolbox.centralfunctions as cf
import toolbox.files as f

# Enter arguments
path = Path(askdirectory(title="Select Folder"))
NUMBER = int(integerbox("Enter how many files you want to collect.", upperbound=9999))

# Create file list
print("Loading file list... ", end="")
collected_files = []
all_files = f.list_files(path, include_subdirs=False)
random.shuffle(all_files)
print("Done!")

# Collect files
for i, file in enumerate(all_files):
    cf.progress_bar(i, NUMBER, "Collecting files...")
    if i >= NUMBER:
        break
    else:
        collected_files.append(file)

# Move files to temp
temppath = path / f"temp-{cf.id_generator(6)}"
temppath.mkdir(parents=True, exist_ok=True)
for i, file in enumerate(collected_files):
    cf.progress_bar(i + 1, NUMBER, "Moving files...")
    shutil.move(file, temppath)

# Zip
print(f"{datetime.datetime.now()} - Creating zip file (may take a couple of minutes)... ", end="")
shutil.make_archive(str(temppath), "zip", temppath)  # can take up to 10 min
print("Done!")
