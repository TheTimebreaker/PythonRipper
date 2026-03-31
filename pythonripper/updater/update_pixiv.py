import asyncio

import pythonripper.extractor.pixiv as pixiv
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.scraperclasses as scraper


async def update_pixiv_artists(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, pixiv.PixivAPI, "artists")


async def main(config: cfg.Config) -> None:
    await update_pixiv_artists(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
