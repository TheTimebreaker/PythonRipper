import asyncio
import inspect
import logging

from pythonripper.extractor import shellvi, supersatanson
import pythonripper.extractor.toolbox.centralfunctions as cf
import pythonripper.extractor.toolbox.config as cfg
from pythonripper.extractor import tangsgallery
from pythonripper.extractor.toolbox.scraperclasses import ArtistWebsiteScraper


async def artist_website_updater(config: cfg.Config, cls: type[ArtistWebsiteScraper]) -> bool | tuple[bool, str]:
    obj = cls(config)

    print(f"Updating local copy of {obj.ME}.")
    dpath = config.dpath() / "artist-websites" / obj.ME
    if not await obj.init():
        return False
    success = await obj.download_all_posts(dpath=dpath, update=True)
    tmp = inspect.currentframe()
    if not success:
        logging.error("[%s-UPDATER] - Some issue occurred that prevented some images from being correctly downloaded", obj.ME.upper())
    assert tmp
    return success, tmp.f_code.co_name


async def update_shellvi(config: cfg.Config) -> bool | tuple[bool, str]:
    return await artist_website_updater(config, shellvi.ShellViAPI)


async def update_supersatanson(config: cfg.Config) -> bool | tuple[bool, str]:
    return await artist_website_updater(config, supersatanson.SuperSatanSonAPI)


async def update_tangsgallery(config: cfg.Config) -> bool | tuple[bool, str]:
    return await artist_website_updater(config, tangsgallery.TangsGalleryAPI)


async def main(config: cfg.Config) -> None:
    await update_shellvi(config)
    await update_supersatanson(config)
    await update_tangsgallery(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
