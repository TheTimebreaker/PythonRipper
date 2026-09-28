import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.subscription_management as sm
from pythonripper.toolbox.config.paths import _Config


async def main(config: _Config) -> None:
    print("=" * 20)
    print("Artist file")

    obj = sm.CombinedArtistFile(config)
    await obj.write()

    print("=" * 20)
    print("Booru file")

    obj2 = sm.CombinedBooruFile(config)
    await obj2.write()


if __name__ == "__main__":
    config = _Config()
    cf.init_logger(config, "warning", False)
    asyncio.run(main(config))
