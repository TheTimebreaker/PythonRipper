import asyncio

import pythonripper.extractor.kusowanka as kusowanka
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config.paths import _Config


async def update_kusowanka_artists(config: _Config) -> bool:
    return await scraper.update_stuff(config, kusowanka.KusowankaAPI, "artists")


async def update_kusowanka_tags(config: _Config) -> bool:
    return await scraper.update_stuff(config, kusowanka.KusowankaAPI, "tags")


async def main(config: _Config) -> None:
    await update_kusowanka_artists(config)
    await update_kusowanka_tags(config)


if __name__ == "__main__":
    config = _Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
