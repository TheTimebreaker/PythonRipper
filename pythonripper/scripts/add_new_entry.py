import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.subscription_management as sm


def main(config: cfg.Config) -> None:
    inp = input("Do you want to add <artist> or <tag>? Please enter either EXACTLY to choose: ")
    if inp in ("artist", "<artist>", "artists", "<artists>"):
        asyncio.run(add_artists(config))
    elif inp in ("tag", "<tag>", "tags", "<tags>"):
        asyncio.run(add_tag(config))
    else:
        print("No valid choice detected, run again.")


async def add_artists(config: cfg.Config) -> None:
    obj = sm.CombinedArtistFile(config)
    await obj.add_tags()


async def add_tag(config: cfg.Config) -> None:
    obj = sm.CombinedBooruFile(config)
    await obj.add_tags()


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", False)
    main(config)
