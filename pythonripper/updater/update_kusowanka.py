import asyncio

import pythonripper.extractor.kusowanka as kusowanka
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject


async def update_kusowanka_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, kusowanka.KusowankaAPI, "artists")


async def update_kusowanka_tags(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, kusowanka.KusowankaAPI, "tags")


async def main(config: ConfigObject) -> None:
    await update_kusowanka_artists(config)
    await update_kusowanka_tags(config)


if __name__ == "__main__":
    config = ConfigObject()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
