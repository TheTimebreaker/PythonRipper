import inspect
import logging

import extractor.danbooru as danbooru
import toolbox.config as cfg
import toolbox.files as f
import toolbox.subscription_management as sm


async def update_danbooru_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of danbooru artists.")
    print("=" * 50)
    print("=" * 50)

    # Load artists
    obj_artist = sm.CombinedArtistFile(config)
    artists = obj_artist.get_list("danbooru")

    # Download
    obj_api = danbooru.DanbooruAPI(config)
    if not await obj_api.init():
        return False
    full_success = True
    for i, artist in enumerate(artists):
        this_path = config.dpath() / "danbooru" / f.verify_filename(artist)
        print(f"{i+1}/{len(artists)} - {artist} - danbooru")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj_api.download_tag(tag_name=artist, dpath=this_path, update=True)
        if not success:
            full_success = False
            logging.error(
                "[DANBOORU-ARTISTS-UPDATER] - Some issue occurred that prevented some images by artist %s being correctly downloaded.", artist
            )
        print("=" * 50)

    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def update_danbooru_tags(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of danbooru tags.")
    print("=" * 50)
    print("=" * 50)

    # Load tags
    obj_tags = sm.CombinedBooruFile(config)
    tags = obj_tags.get_list(website="danbooru")

    # Download
    obj_api = danbooru.DanbooruAPI(config)
    if not await obj_api.init():
        return False
    full_success = True
    for i, tag in enumerate(tags):
        ignore_blacklist = False
        if tag[:2] == "~~" and tag[-2:] == r"~~":  # Blacklist exclusion
            tag = tag[2:-2]
            ignore_blacklist = True

        this_path = config.dpath() / "danbooru" / f.verify_filename(tag)
        print(f"{i+1}/{len(tags)} - {tag} - danbooru")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj_api.download_tag(tag_name=tag, dpath=this_path, update=True, ignore_blacklist=ignore_blacklist)
        if not success:
            full_success = False
            logging.error("[DANBOORU-TAGS-UPDATER] - Some issue occurred that prevented some images by tag %s being correctly downloaded.", tag)
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name
