import asyncio
import inspect
import logging

import aiofiles

import extractor.newgrounds as newgrounds
import toolbox.centralfunctions as cf
import toolbox.config as cfg
import toolbox.files as f
import toolbox.subscription_management as sm


async def update_newgrounds_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of newgrounds artists.")

    # Load artists
    obj_artists = sm.CombinedArtistFile(config)
    artists = obj_artists.get_list("newgrounds")

    # Download
    obj = newgrounds.NewGroundsAPIArtistArt(config)
    if not await obj.init():
        return False
    full_success = True
    for i, artist in enumerate(artists):
        print(f"{i+1}/{len(artists)} - {artist} - newgrounds art page")
        download_folder = config.dpath() / "newgrounds-artists" / f.verify_filename(artist)
        download_folder.mkdir(parents=True, exist_ok=True)
        success = await obj.download_artist_page(download_folder, artist=artist, update=True)
        if not success:
            full_success = False
            logging.error(
                "[NEWGROUNDS-ARTISTS-UPDATER] - Some issue occurred that prevented some images by artist %s being correctly downloaded.", artist
            )
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def update_newgrounds_favorites(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of newgrounds favorites.")
    # Load favorites
    favorites = []
    async with aiofiles.open(config.newgrounds_favs_path(), newline="") as file:
        contents = await file.read()
        for i, favorite in enumerate(contents.split("\n")):
            if i <= 1:
                continue
            favorites.append(favorite)

    # Download favorites
    obj = newgrounds.NewGroundsAPIArtistArtFavorities(config)
    if not await obj.init():
        return False
    full_success = True
    for i, fav in enumerate(favorites):
        print(f"{i+1}/{len(favorites)} - {fav} - newgrounds favorites")
        download_folder = config.dpath() / "newgrounds-favorites" / f.verify_filename(fav)
        download_folder.mkdir(parents=True, exist_ok=True)

        success = await obj.download_artist_page(download_folder, artist=fav, update=True)
        if not success:
            full_success = False
            logging.error("[NEWGROUNDS-FAVS-UPDATER] - Some issue occurred that prevented some images by fav %s being correctly downloaded.", fav)

        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def main(config: cfg.Config) -> None:
    """Run all three reddit updater functions sequentially."""
    await update_newgrounds_artists(config)
    await update_newgrounds_favorites(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
