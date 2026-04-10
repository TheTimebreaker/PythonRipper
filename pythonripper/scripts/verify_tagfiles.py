import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.subscription_management as sm


async def main(config: cfg.Config) -> None:
    print("=" * 20)
    print("Artist file")

    obj = sm.CombinedArtistFile(config)
    await obj.write()

    print("=" * 20)
    print("Booru file")

    obj2 = sm.CombinedBooruFile(config)
    await obj2.write()


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "warning", False)
    asyncio.run(main(config))
