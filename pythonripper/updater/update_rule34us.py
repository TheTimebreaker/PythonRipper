import asyncio

import pythonripper.extractor.rule34us as rule34us
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config.paths import _Config


async def update_rule34us_artists(config: _Config) -> bool:
    return await scraper.update_stuff(config, rule34us.Rule34usAPI, "artists")


async def update_rule34us_tags(config: _Config) -> bool:
    return await scraper.update_stuff(config, rule34us.Rule34usAPI, "tags")


async def main(config: _Config) -> None:
    await update_rule34us_artists(config)
    await update_rule34us_tags(config)


if __name__ == "__main__":
    config = _Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
