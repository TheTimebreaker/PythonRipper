import asyncio

import pythonripper.extractor.gelbooru as gelbooru
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.scraperclasses as scraper


async def update_gelbooru_artists(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, gelbooru.GelbooruAPI, "artists")


async def update_gelbooru_tags(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, gelbooru.GelbooruAPI, "tags")


async def main(config: cfg.Config) -> None:
    await update_gelbooru_artists(config)
    await update_gelbooru_tags(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
