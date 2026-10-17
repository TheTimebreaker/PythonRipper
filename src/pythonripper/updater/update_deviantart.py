import asyncio

import pythonripper.extractor.deviantart as deviantart
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject, config


async def update_deviantart_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, deviantart.DeviantartArtistAPI, "artists")


async def update_deviantart_favorites(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, deviantart.DeviantartFavoritesAPI, "favorites")


async def update_deviantart_tags(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, deviantart.DeviantartTagAPI, "tags")


async def main(config: ConfigObject) -> None:
    await update_deviantart_artists(config)
    await update_deviantart_favorites(config)
    await update_deviantart_tags(config)


if __name__ == "__main__":
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
