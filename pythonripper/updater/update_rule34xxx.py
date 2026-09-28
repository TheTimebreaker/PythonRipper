import asyncio

import pythonripper.extractor.rule34xxx as rule34xxx
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject


async def update_rule34xxx_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, rule34xxx.Rule34xxxAPI, "artists")


async def update_rule34xxx_tags(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, rule34xxx.Rule34xxxAPI, "tags")


async def main(config: ConfigObject) -> None:
    await update_rule34xxx_artists(config)
    await update_rule34xxx_tags(config)


if __name__ == "__main__":
    config = ConfigObject()
    cf.init_logger(config, "warning", False)
    asyncio.run(main(config))
