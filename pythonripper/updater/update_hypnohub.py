import asyncio

import pythonripper.extractor.hypnohub as hypnohub
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject


async def update_hypnohub_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, hypnohub.HypnohubAPI, "artists")


async def update_hypnohub_tags(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, hypnohub.HypnohubAPI, "tags")


async def main(config: ConfigObject) -> None:
    await update_hypnohub_artists(config)
    await update_hypnohub_tags(config)


if __name__ == "__main__":
    config = ConfigObject()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
