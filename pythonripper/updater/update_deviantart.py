import asyncio
import logging

import aiofiles

import pythonripper.extractor.deviantart as deviantart
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


async def update_deviantart_artists(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, deviantart.DeviantartAPI, "artists")


async def update_deviantart_favorites(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of deviantart favorites.")
    print("=" * 50)
    print("=" * 50)

    favorites = []
    async with aiofiles.open(config.deviantart_favs_path(), newline="") as file:
        contents = await file.read()
        for i, fav in enumerate(contents.split("\n")):
            if i <= 1:
                continue
            favorites.append(fav)

    obj = deviantart.DeviantartAPI(config)
    if not await obj.init():
        return False

    full_success = True
    for i, fav in enumerate(favorites):
        print(f"{i+1}/{len(favorites)} - {fav} - deviantart-favorites")
        download_folder = config.dpath() / "deviantart-favorites" / f.verify_filename(fav)
        download_folder.mkdir(parents=True, exist_ok=True)

        success = await obj.download_tag(fav, download_folder, True, custom_mode="deviantart", fetch_favorites=True)
        if not success:
            full_success = False
            logging.error("[DEVIANTART-FAVS-UPDATER] - Some issue occurred that prevented some images by fav %s being correctly downloaded.", fav)
        print("=" * 50)

    return full_success


async def main(config: cfg.Config) -> None:
    await update_deviantart_artists(config)
    await update_deviantart_favorites(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
