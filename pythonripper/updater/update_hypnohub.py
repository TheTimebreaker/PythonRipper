import asyncio

import pythonripper.extractor.hypnohub as hypnohub
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.scraperclasses as scraper


async def update_hypnohub_artists(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, hypnohub.HypnohubAPI, "artists")


async def update_hypnohub_tags(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, hypnohub.HypnohubAPI, "tags")


async def main(config: cfg.Config) -> None:
    await update_hypnohub_artists(config)
    await update_hypnohub_tags(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
