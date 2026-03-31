import asyncio
import inspect
import logging

import aiofiles

import pythonripper.extractor.deviantart as deviantart
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.subscription_management as sm


async def update_deviantart_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of deviantart artists.")
    print("=" * 50)
    print("=" * 50)

    # Load artists
    obj_artist = sm.CombinedArtistFile(config)
    artists = obj_artist.get_list("deviantart")

    # Download
    obj = deviantart.DeviantartAPIGalleryFavourites(config)
    if not await obj.init():
        return False
    full_success = True
    for i, artist in enumerate(artists):
        this_path = config.dpath() / "deviantart-artists" / f.verify_filename(artist)
        link = f"https://www.deviantart.com/{artist}/gallery/all"
        print(f"{i+1}/{len(artists)} - {link} - {artist} - deviantart")

        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_collection(this_path, link, True)
        if not success:
            full_success = False
            logging.error(
                "[DEVIANTART-ARTISTS-UPDATER] - Some issue occurred that prevented some images by artist %s being correctly downloaded.", artist
            )

        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def update_deviantart_favorites(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of deviantart favorites.")
    print("=" * 50)
    print("=" * 50)

    # Load favorites
    favorites = []
    async with aiofiles.open(config.deviantart_favs_path(), newline="") as file:
        contents = await file.read()
        for i, fav in enumerate(contents.split("\n")):
            if i <= 1:
                continue
            favorites.append(fav)

    # Download
    obj = deviantart.DeviantartAPIGalleryFavourites(config)
    if not await obj.init():
        return False
    full_success = True
    for i, fav in enumerate(favorites):
        this_path = config.dpath() / "deviantart-favorites" / f.verify_filename(fav)
        link = f"https://www.deviantart.com/{fav}/favourites/all"
        print(f"{i+1}/{len(favorites)} - {link} - {fav} - deviantart")

        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_collection(this_path, link, True)
        if not success:
            full_success = False
        logging.error("[DEVIANTART-FAVS-UPDATER] - Some issue occurred that prevented some images by fav %s being correctly downloaded.", fav)
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def main(config: cfg.Config) -> None:
    await update_deviantart_artists(config)
    await update_deviantart_favorites(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
