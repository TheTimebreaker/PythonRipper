import asyncio
import logging
from pathlib import Path

import anyio

import pythonripper.extractor.eroprofile as eroprofile
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject, config


async def read_lines(file: Path) -> set[str]:
    if not file.is_file():  # noqa: ASYNC240
        logging.error("[EROPROFILE] - Subscription file at %s not found.", file)
        return set()
    async with await anyio.open_file(file, mode="r", encoding="utf-8") as f:
        return set(await f.readlines())


async def update_eroprofile_photos(config: ConfigObject) -> bool:
    tags = await read_lines(config.paths.eroprofile_photos_path())
    return await scraper.update_stuff(config, eroprofile.EroProfilePictures, "tags", tag_set=tags)


async def update_eroprofile_videos(config: ConfigObject) -> bool:
    tags = await read_lines(config.paths.eroprofile_videos_path())
    return await scraper.update_stuff(config, eroprofile.EroProfileVideos, "tags", tag_set=tags)


async def main(config: ConfigObject) -> None:
    await update_eroprofile_photos(config)
    await update_eroprofile_videos(config)


if __name__ == "__main__":
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
