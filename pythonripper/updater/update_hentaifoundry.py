import asyncio
import inspect
import logging

import pythonripper.extractor.hentaifoundry as hentaifoundry
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.subscription_management as sm


async def update_hentaifoundry_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of hentaifoundry artists.")

    # Load artists
    obj_artists = sm.CombinedArtistFile(config)
    artists = obj_artists.get_list("hentaifoundry")

    # Download
    obj = hentaifoundry.HentaiFoundry(config)
    if not await obj.init():
        return False
    full_success = True
    for i, artist in enumerate(artists):
        this_path = config.dpath() / "hentaifoundry" / f.verify_filename(artist)
        print(f"{i+1}/{len(artists)} - {artist} - hentaifoundry")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_artist_pictures(username=artist, dpath=this_path, update=True)
        if not success:
            full_success = False
            logging.error(
                "[HENTAIFOUNDRY-ARTISTS-UPDATER] - Some issue occurred that prevented some images by artist %s being correctly downloaded.",
                artist,
            )
        print("=" * 50)
    await obj.stop()
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def main(config: cfg.Config) -> None:
    await update_hentaifoundry_artists(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
