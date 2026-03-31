import asyncio
import inspect
import logging

import pythonripper.extractor.patreon as patreon
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.subscription_management as sm


async def update_patreon_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of patreon artists.")

    # Load artists
    obj_artists = sm.CombinedArtistFile(config)
    artists: list[str] = obj_artists.get_list("patreon")
    artists = await patreon.verify_patreon_artist_list(config, artists)

    # Download
    obj = patreon.PatreonAPI(config)
    if not await obj.init():
        return False
    full_success = True
    for i, artist in enumerate(artists):
        print(f"{i+1}/{len(artists)} - {artist} - patreon")
        download_folder = config.dpath() / "patreon" / f.verify_filename(artist)
        download_folder.mkdir(parents=True, exist_ok=True)
        # success = await obj.download_creator_posts(username=artist, dpath=download_folder, update=True)
        if not success:
            full_success = False
            logging.error("[PATREON] - Some issue occurred that prevented some images by artist %s being correctly downloaded.", artist)
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def main(config: cfg.Config) -> None:
    await update_patreon_artists(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
