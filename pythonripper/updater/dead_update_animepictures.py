import asyncio

import pythonripper.extractor.animepictures as animepictures
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject


async def update_animepictures_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, animepictures.Animepictures, "artists")


async def update_animepictures_tags(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, animepictures.Animepictures, "tags")


async def main(config: ConfigObject) -> None:
    await update_animepictures_artists(config)
    await update_animepictures_tags(config)


if __name__ == "__main__":
    config = ConfigObject()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
