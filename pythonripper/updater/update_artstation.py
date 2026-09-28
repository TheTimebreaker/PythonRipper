import asyncio

import pythonripper.extractor.artstation as artstation
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config.paths import _Config


async def update_artstation_artists(config: _Config) -> bool:
    return await scraper.update_stuff(config, artstation.ArtstationAPI, "artists")


async def main(config: _Config) -> None:
    await update_artstation_artists(config)


if __name__ == "__main__":
    config = _Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
