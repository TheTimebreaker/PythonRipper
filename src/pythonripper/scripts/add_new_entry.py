import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.subscription_management as sm
from pythonripper.toolbox.config import ConfigObject, config


async def main(config: ConfigObject) -> None:
    inp = input("Do you want to add <artist> or <tag>? Please enter either EXACTLY to choose: ")  # noqa: ASYNC250
    if inp in ("artist", "<artist>", "artists", "<artists>"):
        await add_artists(config)
    elif inp in ("tag", "<tag>", "tags", "<tags>"):
        await add_tag(config)
    else:
        print("No valid choice detected, run again.")


async def add_artists(config: ConfigObject) -> None:
    obj = sm.CombinedArtistFile(config)
    await obj.add_tags()


async def add_tag(config: ConfigObject) -> None:
    obj = sm.CombinedBooruFile(config)
    await obj.add_tags()


if __name__ == "__main__":
    cf.init_logger(config, "error", False)
    asyncio.run(main(config))
