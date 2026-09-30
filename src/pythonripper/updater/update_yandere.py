import asyncio

import pythonripper.extractor.yandere as yandere
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject, config


async def update_yandere_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, yandere.YandereAPI, "artists")


async def update_yandere_tags(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, yandere.YandereAPI, "tags")


async def main(config: ConfigObject) -> None:
    await update_yandere_artists(config)
    await update_yandere_tags(config)


if __name__ == "__main__":
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
