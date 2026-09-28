import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.subscription_management as sm
from pythonripper.toolbox.config.paths import _Config


def main(config: _Config) -> None:
    inp = input("Do you want to add <artist> or <tag>? Please enter either EXACTLY to choose: ")
    if inp in ("artist", "<artist>", "artists", "<artists>"):
        asyncio.run(add_artists(config))
    elif inp in ("tag", "<tag>", "tags", "<tags>"):
        asyncio.run(add_tag(config))
    else:
        print("No valid choice detected, run again.")


async def add_artists(config: _Config) -> None:
    obj = sm.CombinedArtistFile(config)
    await obj.add_tags()


async def add_tag(config: _Config) -> None:
    obj = sm.CombinedBooruFile(config)
    await obj.add_tags()


if __name__ == "__main__":
    config = _Config()
    cf.init_logger(config, "error", False)
    main(config)
