import asyncio

import pythonripper.extractor.kemono as kemono
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.scraperclasses as scraper


async def update_kemono_afdian(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoAfdian, "artists")


async def update_kemono_boosty(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoBoosty, "artists")


async def update_kemono_dlsite(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoDlsite, "artists")


async def update_kemono_pixiv(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoPixivfanbox, "artists")


async def update_kemono_fantia(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoFantia, "artists")


async def update_kemono_gumroad(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoGumroad, "artists")


async def update_kemono_patreon(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoPatreon, "artists")


async def update_kemono_subscribestar(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, kemono.KemonoSubscribestar, "artists")


async def main(config: cfg.Config) -> None:
    await update_kemono_patreon(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", False)
    asyncio.run(main(config))
