import asyncio

import pythonripper.extractor.tumblr as tumblr
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config.paths import _Config


async def update_tumblr_artists(config: _Config) -> bool | tuple[bool, str]:
    return await scraper.update_stuff(config, tumblr.TumblrAPI, "artists")


async def main(config: _Config) -> None:
    await update_tumblr_artists(config)


if __name__ == "__main__":
    config = _Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
