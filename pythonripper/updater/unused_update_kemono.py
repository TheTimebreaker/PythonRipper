# too unreliable

import asyncio

import pythonripper.extractor.kemono as kemono
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config.paths import _Config


async def update_kemono_afdian(config: _Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoAfdian, "artists")


async def update_kemono_boosty(config: _Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoBoosty, "artists")


async def update_kemono_dlsite(config: _Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoDlsite, "artists")


async def update_kemono_pixiv(config: _Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoPixivfanbox, "artists")


async def update_kemono_fantia(config: _Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoFantia, "artists")


async def update_kemono_gumroad(config: _Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoGumroad, "artists")


async def update_kemono_patreon(config: _Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoPatreon, "artists")


async def update_kemono_subscribestar(config: _Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoSubscribestar, "artists")


async def main(config: _Config) -> None:
    await update_kemono_patreon(config)


if __name__ == "__main__":
    config = _Config()
    cf.init_logger(config, "debug", False)
    asyncio.run(main(config))
