import asyncio

import pythonripper.extractor.gelbooru as gelbooru
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject


async def update_gelbooru_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, gelbooru.GelbooruAPI, "artists")


async def update_gelbooru_tags(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, gelbooru.GelbooruAPI, "tags")


async def main(config: ConfigObject) -> None:
    await update_gelbooru_artists(config)
    await update_gelbooru_tags(config)


if __name__ == "__main__":
    config = ConfigObject()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
