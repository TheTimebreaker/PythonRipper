import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.extractor import akairiot, shellvi, supersatanson, tangsgallery
from pythonripper.toolbox.config.paths import ConfigObject


async def update_akairiot(config: ConfigObject) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, akairiot.AkaiRiot)


async def update_shellvi(config: ConfigObject) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, shellvi.ShellViAPI)


async def update_supersatanson(config: ConfigObject) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, supersatanson.SuperSatanSonAPI)


async def update_tangsgallery(config: ConfigObject) -> bool | tuple[bool, str]:
    return await scraper.artist_website_updater(config, tangsgallery.TangsGalleryAPI)


async def main(config: ConfigObject) -> None:
    await update_akairiot(config)
    await update_shellvi(config)
    await update_supersatanson(config)
    await update_tangsgallery(config)


if __name__ == "__main__":
    config = ConfigObject()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
