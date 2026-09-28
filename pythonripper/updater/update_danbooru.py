import asyncio

import pythonripper.extractor.danbooru as danbooru
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config.paths import _Config


async def update_danbooru_artists(config: _Config) -> bool:
    return await scraper.update_stuff(config, danbooru.DanbooruAPI, "artists")


async def update_danbooru_tags(config: _Config) -> bool:
    return await scraper.update_stuff(config, danbooru.DanbooruAPI, "tags")


async def main(config: _Config) -> None:
    await update_danbooru_artists(config)
    await update_danbooru_tags(config)


if __name__ == "__main__":
    config = _Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
