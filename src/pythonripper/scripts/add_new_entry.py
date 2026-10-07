import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.subscription_management as sm
from pythonripper.toolbox.config import config


async def main() -> None:
    inp = input("Do you want to add <artist> or <tag>? Please enter either EXACTLY to choose: ")  # noqa: ASYNC250
    if inp in ("artist", "<artist>", "artists", "<artists>"):
        await add_artists()
    elif inp in ("tag", "<tag>", "tags", "<tags>"):
        await add_tag()
    else:
        print("No valid choice detected, run again.")


async def add_artists() -> None:
    obj = sm.combined_artist_file
    await obj.add_tags()


async def add_tag() -> None:
    obj = sm.combined_tags_file
    await obj.add_tags()


if __name__ == "__main__":
    cf.init_logger(config, "error", False)
    asyncio.run(main())
