import inspect
import logging

import pythonripper.extractor.hypnohub as hypnohub
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.subscription_management as sm


async def update_hypnohub_artists(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of hypnohub artists.")

    # Load artists
    obj_artists = sm.CombinedArtistFile(config)
    artists = obj_artists.get_list("hypnohub")

    # Download
    obj = hypnohub.HypnohubAPI(config)
    if not await obj.init():
        return False
    full_success = True
    for i, artist in enumerate(artists):
        this_path = config.dpath() / "hypnohub" / f.verify_filename(artist)
        print(f"{i+1}/{len(artists)} - {artist} - hypnohub")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_tag(tag_name=artist, dpath=this_path, update=True)
        if not success:
            full_success = False
            logging.error(
                "[HYPNOHUB-ARTISTS-UPDATER] - Some issue occurred that prevented some images by artist %s being correctly downloaded.", artist
            )
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name


async def update_hypnohub_tags(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of hypnohub tags.")

    # Load tags
    obj_tags = sm.CombinedBooruFile(config)
    tags = obj_tags.get_list(website="hypnohub")

    # Download
    obj = hypnohub.HypnohubAPI(config)
    if not await obj.init():
        return False
    full_success = True
    for i, tag in enumerate(tags):
        ignore_blacklist = False
        if tag[:2] == "~~" and tag[-2:] == "~~":  # Blacklist exclusion
            tag = tag[2:-2]
            ignore_blacklist = True

        this_path = config.dpath() / "hypnohub" / f.verify_filename(tag)
        print(f"{i+1}/{len(tags)} - {tag} - hypnohub")
        this_path.mkdir(parents=True, exist_ok=True)
        success = await obj.download_tag(tag_name=tag, dpath=this_path, update=True, ignore_blacklist=ignore_blacklist)
        if not success:
            full_success = False
            logging.error("[HYPNOHUB-TAGS-UPDATER] - Some issue occurred that prevented some images by tag %s being correctly downloaded.", tag)
        print("=" * 50)
    tmp = inspect.currentframe()
    assert tmp
    return full_success, tmp.f_code.co_name
