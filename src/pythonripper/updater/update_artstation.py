import asyncio

import pythonripper.extractor.artstation as artstation
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject, config


async def update_artstation_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, artstation.ArtstationAPI, "artists")


async def main(config: ConfigObject) -> None:
    await update_artstation_artists(config)


if __name__ == "__main__":
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
