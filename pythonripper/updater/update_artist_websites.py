import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.extractor import akairiot, shellvi, supersatanson, tangsgallery
from pythonripper.toolbox.config.paths import _Config


async def update_akairiot(config: _Config) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, akairiot.AkaiRiot)


async def update_shellvi(config: _Config) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, shellvi.ShellViAPI)


async def update_supersatanson(config: _Config) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, supersatanson.SuperSatanSonAPI)


async def update_tangsgallery(config: _Config) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, tangsgallery.TangsGalleryAPI)


async def main(config: _Config) -> None:
    await update_akairiot(config)
    await update_shellvi(config)
    await update_supersatanson(config)
    await update_tangsgallery(config)


if __name__ == "__main__":
    config = _Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
