import asyncio

import pythonripper.extractor.rule34xyz as rule34xyz
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject, config


async def update_rule34xyz_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, rule34xyz.Rule34xyzAPI, "artists")


async def update_rule34xyz_tags(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, rule34xyz.Rule34xyzAPI, "tags")


async def main(config: ConfigObject) -> None:
    await update_rule34xyz_artists(config)
    await update_rule34xyz_tags(config)


if __name__ == "__main__":
    cf.init_logger(config, "warning", False)
    asyncio.run(main(config))
