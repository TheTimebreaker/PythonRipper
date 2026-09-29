import asyncio
import logging
import re
import shutil
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Self

import duplicate_image_finder as dif
import send2trash
from PIL import Image, UnidentifiedImageError
from psd_tools import PSDImage

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.subscription_management as sm
from pythonripper.toolbox.config import ConfigObject, config


class ExitError(Exception):
    pass


class Log:
    def __init__(self, config: ConfigObject) -> None:
        self.filepath = config.paths.process_downloads_log()
        self.encoding = "utf-8"
        self.read()

    def read(self) -> None:
        if not self.filepath.is_file():
            self.status = 0
            return
        with open(self.filepath, encoding=self.encoding) as file:
            self.status = int(file.read().split("\n")[0])

    async def write(self) -> None:
        await f.atomic_write(filepath=self.filepath, data=str(self.status), encoding=self.encoding)

    async def increment_status(self) -> None:
        self.status += 1
        await self.write()

    def delete(self) -> None:
        f.backup_file(self.filepath)
        self.filepath.unlink()


class Worker:
    def __init__(self, config: ConfigObject) -> None:
        logging.info("Start main.")
        self.config = config
        self.unwanted_formats = self.config.settings.general.exclusions.unwanted_file_extensions
        self.path_download = self.config.paths.downloads()
        self.path_tempdownload = self.config.paths.downloads_temp()
        self.path_storage = self.config.paths.storage()
        self.path_done = self.config.paths.done_path()
        self.log = Log(self.config)

        self.boorus = [
            "booru",
            "danbooru",
            "gelbooru",
            "hypnohub",
            "kusowanka",
            "rule34paheal",
            "rule34us",
            "rule34xxx",
            "rule34xyz",
            "yandere",
        ]
        self.websites = [
            "!archive",
            "artists",
            "artist-websites",
            "artstation",
            "deviantart",
            "deviantart-favorites",
            "hentaifoundry",
            "newgrounds",
            "newgrounds-favorites",
            "patreon",
            "pixiv",
            "reddit",
            "tumblr",
        ]
        self.websites.extend(self.boorus)
        self.websites.sort()

    async def run(self) -> None:
        tasks: tuple[tuple[Callable[..., None], tuple[Any, ...], dict[str, Any]], ...] = (
            (
                self.move_files,
                (self.path_download, self.path_tempdownload),
                {"exclude_files": [".pythonripper"], "move_with_id_files": ["!hashes"]},
            ),
            (self.remove_unwanted_file_formats, (self.path_tempdownload, self.unwanted_formats), {}),
            (self.remove_unwanted_file_formats, (self.path_storage, self.unwanted_formats), {}),
            (self.remove_unwanted_file_formats, (self.path_done, self.unwanted_formats), {}),
            (self.convert_files, (self.path_tempdownload,), {}),
            (self.merge_folders, (self.path_tempdownload,), {}),
            (self.check_file_name_length, (self.path_tempdownload, 100), {}),
            (self.check_duplicates, (self.path_tempdownload,), {}),
            (self.check_duplicates, (self.path_tempdownload, self.path_storage, self.path_done), {}),
            (self.move_files, (self.path_tempdownload, self.path_storage), {"move_with_id_files": ["!hashes"]}),
            (shutil.rmtree, (self.path_tempdownload, True), {}),
            (self.merge_folders, (self.path_storage,), {}),
            (self.merge_folders, (self.path_done,), {}),
            (self.convert_files, (self.path_storage,), {}),
            (self.convert_files, (self.path_done,), {}),
            (self.check_file_name_length, (self.path_done, 100), {}),
            (self.check_file_name_length, (self.path_storage, 100), {}),
        )
        for i, elements in enumerate(tasks):
            if i < self.log.status:
                continue
            func, args, kwargs = elements
            func(*args, **kwargs)
            await self.log.increment_status()

        self.log.delete()

    def move_files(
        self,
        src_dir: Path,
        dst_dir: Path,
        exclude_files: list[str] | tuple[str, ...] | None = None,
        move_with_id_files: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        def should_exclude(file: Path) -> bool:
            if exclude_files is None:
                raise
            return any(exclude_file in file.name for exclude_file in exclude_files)

        def should_move_but_with_id(file: Path) -> bool:
            assert move_with_id_files
            return any(moveBut_file in file.name for moveBut_file in move_with_id_files)

        print(f"Moving files from {src_dir} to {dst_dir} .")
        if exclude_files is None:
            exclude_files = []
        if move_with_id_files is None:
            move_with_id_files = []

        for file in f.iter_files(src_dir):
            if not file.is_file():
                continue

            relative_path = file.parent.relative_to(src_dir)
            dest_path = dst_dir / relative_path
            dest_path.mkdir(parents=True, exist_ok=True)

            print(f"Currently moving: {file.parent} ...", end="\r")
            if should_move_but_with_id(file):
                ext = f.match_extension(file.name)
                dst_path_file = dest_path / file.with_name(file.name.replace(f".{ext}", f"-{cf.id_generator(6)}.{ext}")).name

            elif not should_exclude(file):
                dst_path_file = dest_path / file.name
            else:
                continue
            shutil.move(file, dst_path_file)

    def remove_unwanted_file_formats(self, path: Path, unwanted_extensions: Iterable[str] | None = None) -> None:
        print("Removing unwanted file formats.")
        if unwanted_extensions:
            for file in f.iter_files(path):
                mat = f.match_extension(file.name)
                if mat and mat in unwanted_extensions:
                    file.unlink()
        print("=" * 25)

    def _convert_images(self, path: Path) -> None:
        print(f"Converting image files in {path}.")
        settings = self.config.settings.general.image_conversion_settings
        if settings.enabled is False:
            print("No image file conversion conducted due to settings.")
        else:
            if settings.target_format == ".jpg":
                list_files = f.list_files(path)
                len_list_files = len(list_files)
                lasttime = time.time()
                timing_seconds = 10
                for i, file in enumerate(list_files):
                    if cf.progress_bar_timed(lasttime, timing_seconds, i + 1, len_list_files, "Converting files"):
                        lasttime = time.time()
                    image_converter(file, goal_format=settings.target_format, delete_source=True, quality_setting=settings.target_quality)

            else:
                print(f"Selected target file format not supported: {settings.target_format}")
        print("=" * 25)

    def convert_files(self, path: Path) -> None:
        self._convert_images(path)

    def merge_folders(self, path: Path) -> None:
        def merge_folders_artists(self: Self, path: Path) -> None:
            print("Merging folders...", end="")
            longest_message = 5

            # Artist merge
            combined_artists = sm.CombinedArtistFile(config)
            artists = combined_artists.data

            for artist, artist_dict in artists.items():
                for website, username in artist_dict.items():
                    cm = f"Merging artist folders... currently working at {artist}/{website}.."
                    if len(cm) > longest_message:
                        longest_message = len(cm)
                    print(f'{cm}{"."*(longest_message - len(cm) + 2)}', end="\r")
                    if username:
                        if website == "deviantart":
                            website = "deviantart-artists"
                        if website == "newgrounds":
                            website = "newgrounds-artists"
                        if isinstance(username, (str, int)):
                            username = [username]

                        for element in username:
                            element = str(element)
                            if website == "reddit" and element.startswith("u/"):
                                element = f"u_{element[2:]}"
                            elif website == "reddit" and element.startswith("r/"):
                                element = element[2:]

                            to_dir = path / "artists" / f.verify_filename(artist)
                            from_dir = path / website / f.verify_filename(element)
                            if from_dir.is_dir():
                                self.move_files(src_dir=from_dir, dst_dir=to_dir, exclude_files=[".pythonripper"], move_with_id_files=["!hashes"])
            print("")

        def merge_folders_booru(self: Self, path: Path) -> None:
            print("Merging booru folders...", end="")
            longest_message = 5

            # Artist merge
            combined_artists = sm.CombinedBooruFile(config)
            artists = combined_artists.data
            blacklist_bypass_str = self.config.settings.general.allow_blacklist_bypass
            contentfilter_bypass_str = self.config.settings.general.allow_contentfilter_bypass

            for artist, artist_dict in artists.items():
                for website, username in artist_dict.items():
                    cm = f"Merging booru folders... currently working at {artist}/{website}.."
                    if len(cm) > longest_message:
                        longest_message = len(cm)
                    print(f'{cm}{"."*(longest_message - len(cm) + 2)}', end="\r")
                    if username:
                        if website == "deviantart":
                            website = "deviantart-artists"
                        if website == "newgrounds":
                            website = "newgrounds-artists"
                        if isinstance(username, (str, int)):
                            username = [username]

                        for element in username:
                            element = str(element)
                            for bypass_str in (contentfilter_bypass_str, blacklist_bypass_str, contentfilter_bypass_str):
                                if bypass_str and element.startswith(bypass_str) and element.endswith(bypass_str):
                                    leng = len(bypass_str)
                                    element = element[leng:-leng]

                            if website == "reddit" and element.startswith("u/"):
                                element = f"u_{element[2:]}"
                            elif website == "reddit" and element.startswith("r/"):
                                element = element[2:]

                            to_dir = path / "booru" / f.verify_filename(artist)
                            from_dir = path / website / f.verify_filename(element)
                            if from_dir.is_dir():
                                self.move_files(src_dir=from_dir, dst_dir=to_dir, exclude_files=[".pythonripper"], move_with_id_files=["!hashes"])
                            if website in self.boorus:
                                from_dir = path / "booru" / element
                                if not from_dir == to_dir and from_dir.is_dir():
                                    self.move_files(src_dir=from_dir, dst_dir=to_dir, exclude_files=[".pythonripper"], move_with_id_files=["!hashes"])
            print("")

        merge_folders_artists(self, path)
        merge_folders_booru(self, path)

        print("Merging folders... Deleting empty folders... ", end="")
        for website in self.websites:
            website_path = path / website
            if not website_path.is_dir():
                continue
            for folder in f.iter_directories(website_path):
                if not folder.is_dir():
                    continue
                if f.is_dir_empty(folder):
                    folder.rmdir()

            if f.is_dir_empty(website_path):
                website_path.rmdir()

        print("DONE! ")
        print("=" * 25)

    def check_file_name_length(self, path: Path, char_limit: int = 100) -> None:
        print(f"Checking filename length in {path} ...")

        def single_check(file: Path, char_limit: int) -> None:
            if len(file.stem) > char_limit:
                pattern = r"(?:.)+\-([\d]+)"
                matcher = re.match(pattern, file.stem)
                number = ""
                if matcher and matcher.group(1):
                    number = f"-{matcher.group(1)}"
                char_limit = char_limit - len(number)

                new_name = f"{file.stem[0:char_limit]}{number}"
                new_path = file.with_name(f"{new_name}{file.suffix}")
                if new_path.is_file():
                    new_name = f"{file.stem[0:char_limit-5]}{cf.id_generator(5)}{number}"
                    new_path = file.with_name(f"{new_name}{file.suffix}")

                file.rename(new_path)

        allfiles = f.list_files(path)  # [fullpath, folder where the file is located, filename without ext, ext]
        lenallfiles = len(allfiles)
        lasttime = time.time()
        timing_seconds = 10
        for i, file in enumerate(allfiles):
            if cf.progress_bar_timed(lasttime, timing_seconds, i + 1, lenallfiles, "Filename length"):
                lasttime = time.time()
            single_check(file, char_limit)
        print(f"Checking filename length in {path} ... DONE!")
        print("=" * 25)

    def check_duplicates(self, *paths: Path) -> None:
        print(f"Checking for duplicates in {paths}.")
        dif.find_and_delete_duplicates(paths, "rm", ("pixel_count", "descending"), ("is_file", "descending"), ("filesize", "descending"))
        print("=" * 25)


def image_converter(file: Path, goal_format: str, delete_source: bool, quality_setting: int) -> None:
    Image.MAX_IMAGE_PIXELS = None

    # Takes in feed from fileopener-dialogue and converts and saves it.
    def funnel(
        pipe: Image.Image,
        file: Path,
        goal_format: str,
        quality_setting: int,
    ) -> None:
        img = pipe.convert("RGB")
        file_converted = file.with_name(f"{file.stem}{goal_format}")
        if file_converted.is_file():
            file_converted = file_converted.with_name(f"{file.stem}-{cf.id_generator()}.{goal_format}")
        if goal_format == ".png":
            img.save(file_converted)
        elif goal_format == ".jpg":
            img.save(file_converted, quality=quality_setting)

    try:
        if (not file.suffix.lower() == goal_format) and file.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff", ".gif"):
            with Image.open(file) as img:
                funnel(
                    pipe=img,
                    file=file,
                    goal_format=goal_format,
                    quality_setting=quality_setting,
                )
        elif (not file.suffix.lower() == goal_format) and file.suffix.lower() in (".psd"):
            psd = PSDImage.open(file)
            funnel(
                pipe=psd.composite(),
                file=file,
                goal_format=goal_format,
                quality_setting=quality_setting,
            )
        else:  # Skips delete, if file extension not supported
            return

        if str(delete_source) == "bin":
            send2trash.send2trash(file)
        elif delete_source:
            file.unlink(missing_ok=True)

    except BrokenPipeError:
        logging.error("BrokenPipeError: '%s'", file)
    except UnidentifiedImageError:
        logging.error("UnidentifiedImageError: '%s'", file)
    except PermissionError:
        logging.error("PermissionError: '%s'", file)
    except SyntaxError:
        logging.error("SyntaxError: '%s'", file)
    except ValueError:
        logging.error("ValueError: '%s'", file)
    except OSError:
        logging.error("OSError: '%s'", file)


if __name__ == "__main__":
    cf.init_logger(config, "error", True)
    worker = Worker(config)
    asyncio.run(worker.run())
