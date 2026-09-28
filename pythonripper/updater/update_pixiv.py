import asyncio

import pythonripper.extractor.pixiv as pixiv
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config.paths import ConfigObject


async def update_pixiv_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, pixiv.PixivArtistAPI, "artists")


async def update_pixiv_tags(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, pixiv.PixivTagAPI, "tags")


async def main(config: ConfigObject) -> None:
    await update_pixiv_artists(config)
    await update_pixiv_tags(config)


if __name__ == "__main__":
    config = ConfigObject()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
