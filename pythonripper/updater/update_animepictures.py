import asyncio

import pythonripper.extractor.animepictures as animepictures
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.scraperclasses as scraper


async def update_animepictures_artists(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, animepictures.Animepictures, "artists")


async def update_animepictures_tags(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, animepictures.Animepictures, "tags")


async def main(config: cfg.Config) -> None:
    await update_animepictures_artists(config)
    await update_animepictures_tags(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
