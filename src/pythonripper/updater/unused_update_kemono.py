# too unreliable

import asyncio

import pythonripper.extractor.kemono as kemono
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject, config


async def update_kemono_afdian(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoAfdian, "artists")


async def update_kemono_boosty(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoBoosty, "artists")


async def update_kemono_dlsite(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoDlsite, "artists")


async def update_kemono_pixiv(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoPixivfanbox, "artists")


async def update_kemono_fantia(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoFantia, "artists")


async def update_kemono_gumroad(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoGumroad, "artists")


async def update_kemono_patreon(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoPatreon, "artists")


async def update_kemono_subscribestar(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoSubscribestar, "artists")


async def main(config: ConfigObject) -> None:
    await update_kemono_patreon(config)


if __name__ == "__main__":
    cf.init_logger(config, "debug", False)
    asyncio.run(main(config))
