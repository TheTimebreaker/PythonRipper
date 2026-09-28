import asyncio

import pythonripper.extractor.tumblr as tumblr
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject


async def update_tumblr_artists(config: ConfigObject) -> bool | tuple[bool, str]:
    return await scraper.update_stuff(config, tumblr.TumblrAPI, "artists")


async def main(config: ConfigObject) -> None:
    await update_tumblr_artists(config)


if __name__ == "__main__":
    config = ConfigObject()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
