import asyncio

import pythonripper.extractor.newgrounds as newgrounds
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject, config


async def update_newgrounds_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, newgrounds.NewgroundsArtAPI, "artists")


async def update_newgrounds_favorites(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, newgrounds.NewgroundsFavoriteArtAPI, "favorites")


async def update_newgrounds_tags(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, newgrounds.NewgroundsTagsArtAPI, "tags")


async def main(config: ConfigObject) -> None:
    await update_newgrounds_artists(config)
    await update_newgrounds_favorites(config)
    await update_newgrounds_tags(config)


if __name__ == "__main__":
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
