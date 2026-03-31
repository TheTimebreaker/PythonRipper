import asyncio

import pythonripper.extractor.rule34paheal as rule34paheal
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.scraperclasses as scraper


async def update_rule34paheal_artists(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, rule34paheal.Rule34pahealAPI, "artists")


async def update_rule34paheal_tags(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, rule34paheal.Rule34pahealAPI, "tags")


async def main(config: cfg.Config) -> None:
    await update_rule34paheal_artists(config)
    await update_rule34paheal_tags(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
