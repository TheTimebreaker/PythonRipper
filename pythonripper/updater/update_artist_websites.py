import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.extractor import akairiot, shellvi, supersatanson, tangsgallery


async def update_akairiot(config: cfg.Config) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, akairiot.AkaiRiot)


async def update_shellvi(config: cfg.Config) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, shellvi.ShellViAPI)


async def update_supersatanson(config: cfg.Config) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, supersatanson.SuperSatanSonAPI)


async def update_tangsgallery(config: cfg.Config) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, tangsgallery.TangsGalleryAPI)


async def main(config: cfg.Config) -> None:
    await update_akairiot(config)
    await update_shellvi(config)
    await update_supersatanson(config)
    await update_tangsgallery(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
