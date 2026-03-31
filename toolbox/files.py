"""Central file read/write functions."""

import asyncio
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any, Literal

import aiofiles
import aiofiles.ospath as aiopath
import aioshutil
import curl_cffi

import toolbox.centralfunctions as cf
import toolbox.config as cfg


def match_extension(string: str, before_symbol: str = ".") -> str | None:
    """Matches a lot of known multi-media file extensions and returns if found (without the extension dot)."""
    pattern = "\\" + before_symbol + r"""(jpg|jpeg|jfif|tiff|tif|webp|webm|gifv|gif|mp4|png|txt|swf|bmp|m4a|opus|mp3|aac|db|csv|bak|zip|psd)"""
    string = string.lower()
    matched = re.search(pattern, string)
    if matched:
        return matched.group(1)
    return None


def list_files(input_dir: Path, include_subdirs: bool = True) -> list[Path]:
    """Returns list (fullpath) of all files in a given directory (including subdirs)"""
    return [x for x in iter_files(input_dir, include_subdirs)]


def iter_files(input_dir: Path, include_subdirs: bool = True) -> Generator[Path]:
    """Generator for all files in a given directory (optionally including subdirs)"""
    if include_subdirs:
        # As much as I dislike os for this, it is about 10 times faster compared to Path().rglob("*")
        for root, _dirs, files in os.walk(input_dir):
            for file in files:
                yield Path(root) / file
    else:
        for p in input_dir.iterdir():
            if p.is_file():
                yield p


def list_directories(input_dir: Path, include_subdirs: bool = True) -> list[Path]:
    return [x for x in iter_directories(input_dir, include_subdirs)]


def iter_directories(input_dir: Path, include_subdirs: bool = True) -> Generator[Path]:
    """Yields all folders (recursively)"""
    if include_subdirs:
        # As much as I dislike os for this, it is about 10 times faster compared to Path().rglob("*")
        for root, dirs, _files in os.walk(input_dir):
            for dir in dirs:
                yield Path(root) / dir
    else:
        for p in input_dir.iterdir():
            if p.is_dir():
                yield p


def is_dir_empty(directory: Path) -> bool:
    """Checks whether a folder path leads to an empty folder."""
    if directory.is_dir():
        return not any(directory.iterdir())
    return False


def verify_filename(filename: str, replace_by: str = "_") -> str:
    """Returns verified version of input filename (replaces chars, that cause problems in Windows, Linux and MacOS)"""

    # Replaces illegal characters (or at least all chars, that may cause problems, but aren't absolutely impossible)
    illegal_characters_linux = ["/"]
    illegal_characters_windows = ["<", ">", ":", '"', "/", "\\", "|", "?", "*", "\n", "\t"]
    illegal_characters_macos = [":", "/"]
    for char in illegal_characters_linux + illegal_characters_macos + illegal_characters_windows:
        filename = filename.replace(char, replace_by)

    # If the filename ends with a dot or space, this may cause problems in Windows
    while filename[-1] in (".", " "):
        filename = filename[0:-1]
    while filename[0] == " ":
        filename = filename[1:]
    while ".." in filename:
        filename = filename.replace("..", "_.")

    # Some double filename extensions
    extension_map = {"jpeg": "jpg", "jpe": "jpg", "jfif": "jpg", "jif": "jpg", "jfi": "jpg", "tif": "tiff"}
    for extension, mapped in extension_map.items():
        if filename.endswith(f".{extension}"):
            filename = filename.replace(f".{extension}", f".{mapped}")

    other_map = {"%2C": ","}
    for what, by in other_map.items():
        filename = filename.replace(what, by)

    return filename


def backup_file(file: Path) -> None:
    filebak = file.with_name(file.name + ".bak")
    if file.is_file():
        if "win32" in sys.platform:
            if filebak:
                try:
                    subprocess.check_call(["attrib", "-H", str(filebak)])  # makes bak file unhidden so shutil can work
                except FileNotFoundError:
                    pass
            shutil.copy(file, filebak)
        elif "linux" in sys.platform:
            shutil.copy(file, filebak)
        else:
            raise Exception(f"Cant progress, system: {sys.platform} not implemented")


async def atomic_write(
    filepath: Path, data: str | bytes | dict[Any, Any], encoding: str | None = "utf-8", newline: str | None = None, append: bool = False
) -> None:
    """Write data to a file atomically, creating a .bak backup if the file exists."""
    if await aiopath.isdir(filepath):
        raise ValueError("Cannot write file contents to a directory.")

    # Backup
    if await aiopath.isfile(filepath):
        backup_path = filepath.with_suffix(filepath.suffix + ".bak")
        if await aiopath.isfile(backup_path):
            try:
                await asyncio.to_thread(backup_path.unlink)
            except PermissionError:
                await asyncio.to_thread(subprocess.run, ["attrib", "-H", str(backup_path.resolve())], check=True)
                await asyncio.to_thread(backup_path.unlink)
        await aioshutil.copy2(filepath, backup_path)

    # Actual writing process
    if append is True:
        tmp_path = filepath.with_suffix(filepath.suffix + ".tmp")
        try:
            await aioshutil.copy2(filepath, tmp_path)
        except FileNotFoundError:
            pass

        if isinstance(data, str):
            write_type = "a"
        elif isinstance(data, bytes):
            write_type = "ab"
            encoding = None
            newline = None
        elif isinstance(data, dict):
            write_type = "a"
            data = json.dumps(data, indent=4)
        else:
            raise TypeError("Tried to write invalid data to %s.", filepath)

        async with aiofiles.open(tmp_path, mode=write_type, encoding=encoding, newline=newline) as file:  # type: ignore
            file: aiofiles.threadpool.binary.AsyncBufferedReader  # type: ignore
            await file.write(data)

    else:
        if isinstance(data, str):
            write_type = "w"
        elif isinstance(data, bytes):
            write_type = "wb"
            encoding = None
            newline = None
        elif isinstance(data, dict):
            write_type = "w"
            data = json.dumps(data, indent=4)
        async with aiofiles.tempfile.NamedTemporaryFile(
            write_type, encoding=encoding, dir=filepath.parent, delete=False, newline=newline
        ) as tmp_file:  # type: ignore
            tmp_file: aiofiles.threadpool.binary.AsyncBufferedReader  # type: ignore
            await tmp_file.write(data)
            tmp_path = Path(tmp_file.name)

    try:
        await asyncio.to_thread(tmp_path.replace, filepath)
    except Exception:
        if await aiopath.isfile(tmp_path):
            await asyncio.to_thread(tmp_path.unlink)


async def download_file(
    config: cfg.Config | None = None,
    url: str | None = None,
    headers: dict[str, str] | None = None,
    path: Path | None = None,
    filename: str = cf.id_generator(20),
    force_overwrite: bool = False,
    request_content: bytes | None = None,
    no_impersonation: bool = False,
) -> bool:  # Return True/False, depending on whether request was successful or not
    """Function, that downloads FILENAME to PATH/FILENAME found at URL using HEADERS in it's HTML request. Returns bool for success/failure"""
    if config is None:
        raise ValueError
    if headers is None:
        headers = {}
    if path is None:
        path = config.test_dir()
    path.mkdir(exist_ok=True, parents=True)
    if filename.endswith("None"):
        raise TypeError("Filename parameter in download was None, this is almost certainly a bug and not intended.")
    if filename.endswith(".jpeg"):
        filename = filename.replace(".jpeg", ".jpg")
    filename = verify_filename(filename)
    path_to_filename = path / filename

    config_allows_overwrites = config and config.data["general"]["overwriteExistingFiles"]
    file_exists = await aiopath.isfile(path_to_filename)
    if force_overwrite or config_allows_overwrites or not file_exists:
        logging.debug(url)
        for i in range(5, 60, 5):
            if request_content:
                await atomic_write(path_to_filename, request_content)
                logging.debug("Download of file url %s successful.", url)
                return True
            elif url:
                try:
                    logging.info("[DOWNLOAD_FILE] - no_impersonation flag set to: %s", no_impersonation)
                    logging.info("[DOWNLOAD_FILE] - Impersonate: %s", None if no_impersonation else "chrome101")
                    async with curl_cffi.requests.AsyncSession(impersonate=None if no_impersonation else "chrome101", headers=headers) as session:
                        res = await session.get(url, timeout=cf.asynctimeoutseconds(), allow_redirects=True, http_version=1)
                except curl_cffi.requests.exceptions.Timeout:
                    await asyncio.sleep(i)
                    continue
                except curl_cffi.requests.exceptions.ConnectionError:
                    logging.warning("ConnectionError when downloading url %s ...", url)
                    return False
                if res and res.status_code == 200:
                    await atomic_write(path_to_filename, res.content)
                    logging.debug("Download of file url %s successful.", url)
                    return True
                elif res.status_code in (403, 404):  # these codes are important enough for an ERROR msg
                    logging.error("download_file encountered a %s. Download cancelled. Url: %s", res.status_code, url)
                    return False
                elif res.status_code == 429:
                    logging.warning("download_file encountered a %s. Timeouting. Url: %s", res.status_code, url)
                    await asyncio.sleep(i)
                elif res.status_code > 400:  # Immediately stop when encountering a BIG problem
                    logging.warning("download_file encountered a %s. Download cancelled. Url: %s", res.status_code, url)
                    return False
                else:
                    logging.debug(res.status_code)
                    await asyncio.sleep(i)
            else:
                raise TypeError(f'No "requestContent" was given, but bool(url) "{url=}" is not True.')
        logging.error("Download of file url %s failed due to HTML response.", url)
        return False
    return True


async def download_text(config: cfg.Config, directory: Path, filename: str, content: str, encoding: str = "utf-8") -> bool:
    filename = verify_filename(filename)
    path_to_filename = directory / filename
    if not config.data["general"]["overwriteExistingFiles"] and await aiopath.isfile(path_to_filename):  # Skips, if file already exists
        return True
    await atomic_write(path_to_filename, content, encoding=encoding)
    return True


async def download_link(config: cfg.Config, url: str, link_path: Path | None = None) -> Literal[True]:
    if link_path is None:
        link_path = config.linkspath()
    await atomic_write(filepath=link_path, data=url, encoding="utf-8", append=True)
    return True


async def write_update_file(
    data: list[Any],
    dpath: Path,
    previous_ids: list[Any] | None = None,
    key: str | int | None = None,
    bottom_line: dict[Any, Any] | Literal[False] = False,
) -> None:
    """Writes an update file, appending previous update IDs if necessary.

    Assumes that the first entry in "data" is the newest."""
    if previous_ids is None:
        previous_ids = []
    if len(data) > 0:
        current_ids = []
        if len(data) > 10:
            counter = 10
        else:
            counter = len(data)
        if key is None:
            for i in range(counter):
                current_ids.append(data[i])
        else:
            for i in range(counter):
                current_ids.append(str(data[i][key]))
        current_ids = current_ids + previous_ids[0 : 10 - len(current_ids)]  # Table, containing the ten last downloaded IDs

        curr = ";".join(str(x) for x in current_ids)
        prev = ";".join(str(x) for x in previous_ids)
        write_table = [
            curr,
            f"# Previous ID: {prev}",
            "# This file got automatically generated by PythonRipper (a python reddit ripper script).",
            "# It got generated as a result of the 'update a local copy' setting.",
            "# The post ID of the post at the very top of whichever list downloaded gets saved and updating downloads will stop, once they reach this file.",  # noqa: E501
            "# Keep in mind, that this updating will only work properly in chronologically ordered lists (/new).",
            "# MODIFY AT YOUR OWN RISK!",
        ]
        if bottom_line:
            key = next(iter(bottom_line.keys()))
            value = bottom_line[key]
            s = f"{key}: {value}"
            write_table.append(s)

        content = "\n".join(write_table)
        filepath = dpath / ".pythonripper"
        await atomic_write(filepath, content)


async def read_update_file(dpath: Path, bottom_line: bool = False) -> list[str] | tuple[list[str], str]:
    pythonripper_file_path = dpath / ".pythonripper"
    pythonripper_file_path_bak = dpath / ".pythonripper.bak"
    try:
        async with aiofiles.open(pythonripper_file_path) as f:
            content = await f.read()
            content_lines = content.splitlines()
            update_ids = content_lines[0].split(";")
            if bottom_line:
                bottom_line_content = content_lines[-1].split(": ")[-1]
                return update_ids, bottom_line_content
            return update_ids
    except FileNotFoundError:
        try:
            async with aiofiles.open(pythonripper_file_path_bak) as f:
                content = await f.read()
                content_lines = content.splitlines()
                update_ids = content_lines[0].split(";")
                if bottom_line:
                    bottom_line_content = content_lines[-1].split(": ")[-1]
                    return update_ids, bottom_line_content
                return update_ids
        except FileNotFoundError:
            pass
    return []


class SqlDownloadHistory:
    def __init__(self, name: str, config: cfg.Config) -> None:
        self.name = name
        self.path = config._downloadhistory_path() / f"{self.name.lower()}_downloadhistory.db"
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("CREATE TABLE IF NOT EXISTS downloads (id INTEGER PRIMARY KEY)")
        self.conn.commit()

    def add(self, file_id: str) -> None:
        self.conn.execute("INSERT OR IGNORE INTO downloads (id) VALUES (?)", (str(file_id),))
        self.conn.commit()

    def batch_add(self, file_ids: list[str]) -> None:
        for file_id in file_ids:
            self.conn.execute("INSERT OR IGNORE INTO downloads (id) VALUES (?)", (str(file_id),))
        self.conn.commit()

    def contains(self, file_id: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM downloads WHERE id=?", (str(file_id),))
        return cur.fetchone() is not None

    def remove(self, file_id: str) -> None:
        self.conn.execute("DELETE FROM downloads WHERE id=?", (str(file_id),))
