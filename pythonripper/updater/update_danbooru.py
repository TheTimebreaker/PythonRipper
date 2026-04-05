import asyncio

import pythonripper.extractor.danbooru as danbooru
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.scraperclasses as scraper


async def update_danbooru_artists(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, danbooru.DanbooruAPI, "artists")


async def update_danbooru_tags(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, danbooru.DanbooruAPI, "tags")


async def main(config: cfg.Config) -> None:
    await update_danbooru_artists(config)
    await update_danbooru_tags(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
