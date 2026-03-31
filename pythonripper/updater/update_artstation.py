import asyncio
import inspect
import logging

import pythonripper.extractor.artstation as artstation
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.subscription_management as sm


async def update_artstation_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of artstation artists.")
    print("=" * 50)
    print("=" * 50)

    # Load artists
    artist_object = sm.CombinedArtistFile(config)
    artists = artist_object.get_list("artstation")

    # Download
    obj = artstation.ArtstationAPI(config)
    if not await obj.init():
        return False
    full_success = True
    for i, artist in enumerate(artists):
        this_path = config.dpath() / "artstation" / f.verify_filename(artist)
        print(f"{i+1}/{len(artists)} - {artist} - artstation artists")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_artist(dpath=this_path, artist=artist, update=True)
        if not success:
            full_success = False
            logging.error(
                "[ARTSTATION-ARTISTS-UPDATER] - Some issue occurred that prevented some images by artist %s being correctly downloaded.", artist
            )
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def main(config: cfg.Config) -> None:
    await update_artstation_artists(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
