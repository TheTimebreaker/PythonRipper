import asyncio

import pythonripper.extractor.yandere as yandere
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.scraperclasses as scraper


async def update_yandere_artists(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, yandere.YandereAPI, "artists")


async def update_yandere_tags(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, yandere.YandereAPI, "tags")


async def main(config: cfg.Config) -> None:
    await update_yandere_artists(config)
    await update_yandere_tags(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
