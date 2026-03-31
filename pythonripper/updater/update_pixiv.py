import asyncio
import inspect
import logging
import random

import pythonripper.extractor.pixiv as pixiv
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.subscription_management as sm


async def update_pixiv_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of pixiv artists.")

    # #Load artists
    obj_artists = sm.CombinedArtistFile(config)
    artists = obj_artists.get_list("pixiv")
    random.shuffle(artists)

    # Download
    obj = pixiv.PixivAPI(config)
    if not await obj.init():
        return False
    full_success = True
    for i, artist in enumerate(artists):
        this_path = config.dpath() / "pixiv" / f.verify_filename(artist)
        print(f"{i+1}/{len(artists)} - {artist} - pixiv")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_user_illustrations(user_id=artist, dpath=this_path, update=True, manual_username=artist)
        if not success:
            full_success = False
            logging.error("[PIXIV-ARTISTS-UPDATER] - Some issue occurred that prevented some images by artist %s being correctly downloaded.", artist)
        print("=" * 50)
        await asyncio.sleep(1)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def main(config: cfg.Config) -> None:
    await update_pixiv_artists(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
