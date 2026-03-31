import asyncio
import inspect
import logging

import extractor.tumblr as tumblr
import toolbox.centralfunctions as cf
import toolbox.config as cfg
import toolbox.files as f
import toolbox.subscription_management as sm


async def update_tumblr_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of tumblr artists.")
    print("=" * 50)
    print("=" * 50)

    # Load artists
    obj_artists = sm.CombinedArtistFile(config)
    artists = obj_artists.get_list("tumblr")

    # Download
    obj = tumblr.TumblrAPI(config)
    if not await obj.init():
        return False
    full_success = True
    for i, artist in enumerate(artists):
        this_path = config.dpath() / "tumblr" / f.verify_filename(artist)
        print(f"{i+1}/{len(artists)} - {artist} - tumblr")
        this_path.mkdir(parents=True, exist_ok=True)
        # success = await obj.download_user_image_posts(this_path, artist, True) #TODO
        if not success:
            full_success = False
            logging.error(
                "[TUMBLR-ARTISTS-UPDATER] - Some issue occurred that prevented some images by artist %s being correctly downloaded.", artist
            )
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def main(config: cfg.Config) -> None:
    await update_tumblr_artists(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
