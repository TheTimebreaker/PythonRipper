import asyncio
from itertools import chain, combinations, permutations
from typing import Literal

import pythonripper.toolbox.subscription_management as sm
from pythonripper.extractor.kusowanka import KusowankaAPI
from pythonripper.extractor.newgrounds import NewgroundsTagsArtAPI
from pythonripper.toolbox.config import config


async def main() -> None:
    def is_formatted_existing_alias_in_formatted_artist_aliases(formatted_existing_alias: str) -> str | Literal[False]:
        for artist_alias in artist_aliases:
            formatted_artist_alias = obj.format_tagname(artist_alias)
            if formatted_artist_alias and formatted_existing_alias == formatted_artist_alias:
                return artist_alias
        return False

    obj = NewgroundsTagsArtAPI(config)
    await obj.init()

    artist = "adventure time"
    choice = "newgrounds-tags"

    is_case_sensitive = obj.IS_CASE_SENSITIVE
    artist_aliases_tmp: set[str] = {artist, *sm.combined_tags_file.get_list(artist=artist, remove_bypass_markers=True)}
    artist_aliases: set[str] = {
        artist_alias.replace("artist/", "")
        .replace("tag/", "")
        .replace("character/", "")
        .replace("parody/", "")
        .replace("metadata/", "")
        .replace("u/", "")
        .replace("r/", "")
        for artist_alias in artist_aliases_tmp
    }
    # Case sensitive check
    if not is_case_sensitive:
        artist_aliases = {x.lower() for x in artist_aliases}

    # kusowanka special case because they use the category in the url
    if isinstance(obj, KusowankaAPI):
        kusowanka_aliases: set[str] = set()
        for tn in artist_aliases:
            kusowanka_aliases.update(
                (
                    f"artist/{tn}",
                    f"character/{tn}",
                    f"metadata/{tn}",
                    f"parody/{tn}",
                    f"tag/{tn}",
                )
            )
        artist_aliases = kusowanka_aliases

    # Removes any alias that already exists for the website and artist
    list_of_bypass_markers: list[str] = []
    bypass_configs = [
        config.settings.general.allow_blacklist_bypass,
        config.settings.general.allow_contentfilter_bypass,
    ]
    for me in bypass_configs:
        if me:
            list_of_bypass_markers.append(me)
    bypass_permutations = list(
        chain.from_iterable(permutations(combo) for r in range(len(list_of_bypass_markers) + 1) for combo in combinations(list_of_bypass_markers, r))
    )

    print(
        f"artist_aliases before discarding={artist_aliases}",
    )
    discared_aliases: set[str] = set()
    for existing_alias in sm.combined_tags_file.get_list(website=choice, artist=artist, remove_bypass_markers=True):
        # removes the literal existing alias
        discared_aliases.add(existing_alias)

        # formats existing alias and if that matches the preprocessed list, original gets removed
        formatted_existing_alias = obj.format_tagname(existing_alias)
        if formatted_existing_alias:
            discared_aliases.add(formatted_existing_alias)
            placeholder_ = is_formatted_existing_alias_in_formatted_artist_aliases(formatted_existing_alias)
            if placeholder_:
                discared_aliases.add(placeholder_)

        # removes potential flag bypasses from the string
        for combination in bypass_permutations:
            target_tmp = existing_alias
            if combination:
                for element in combination:
                    target_tmp = f"{element}{target_tmp}{element}"
            discared_aliases.add(target_tmp)

    print(f"{discared_aliases=}")
    for discard in discared_aliases:
        artist_aliases.discard(discard)

    print(f"artist_aliases after discarding={artist_aliases}")


asyncio.run(main())
