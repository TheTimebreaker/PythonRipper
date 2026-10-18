# ruff: noqa: E402
# some logging shenanigans is required to prevent all warning from being printed twice

import logging

logging.basicConfig(level=logging.CRITICAL)

import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.subscription_management as sm
from pythonripper.toolbox.config import config


async def main() -> None:
    print("=" * 20)
    print("Artist file")

    obj = sm._CombinedArtistFile(config)
    await obj.write()

    print("=" * 20)
    print("Booru file")

    obj2 = sm._CombinedBooruFile(config)
    await obj2.write()


if __name__ == "__main__":
    cf.init_logger(config, "warning", False)
    asyncio.run(main())
