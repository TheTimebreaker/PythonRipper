import asyncio
import inspect
import logging

import pythonripper.extractor.yandere as yandere
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.subscription_management as sm


async def update_yandere_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of yandere artists.")
    print("=" * 50)
    print("=" * 50)

    # Load artists
    obj_artists = sm.CombinedArtistFile(config)
    artists = obj_artists.get_list("yandere")

    # Download
    full_success = True
    obj = yandere.YandereAPI(config)
    if not await obj.init():
        return False
    for i, artist in enumerate(artists):
        this_path = config.dpath() / "yandere" / f.verify_filename(artist)
        print(f"{i+1}/{len(artists)} - {artist} - yandere artist")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_tag(tagname=artist, dpath=this_path, update=True)
        if not success:
            full_success = False
            logging.error(
                "[YANDERE-ARTISTS-UPDATER] - Some issue occurred that prevented some images by artist %s being correctly downloaded.", artist
            )
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def update_yandere_tags(config: cfg.Config) -> bool | tuple[bool, str]:  # yes this downloads explicit stuff
    print("Updating local copy of yandere tags.")
    print("=" * 50)
    print("=" * 50)

    # Load tags
    obj_tags = sm.CombinedBooruFile(config)
    tags = obj_tags.get_list("yandere")

    # Download
    full_success = True
    obj = yandere.YandereAPI(config)
    if not await obj.init():
        return False
    for i, tag in enumerate(tags):
        ignore_blacklist = False
        if tag[:2] == "~~" and tag[-2:] == "~~":  # Blacklist exclusion
            tag = tag[2:-2]
            ignore_blacklist = True
        this_path = config.dpath() / "yandere" / f.verify_filename(tag)
        print(f"{i+1}/{len(tags)} - {tag} - yandere tags")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_tag(tagname=tag, dpath=this_path, update=True, ignore_blacklist=ignore_blacklist)
        if not success:
            full_success = False
            logging.error("[YANDERE-TAGS-UPDATER] - Some issue occurred that prevented some images by tag %s being correctly downloaded.", tag)
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def main(config: cfg.Config) -> None:
    await update_yandere_artists(config)
    await update_yandere_tags(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
