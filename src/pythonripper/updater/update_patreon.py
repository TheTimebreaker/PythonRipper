import asyncio

import pythonripper.extractor.patreon as patreon
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
import pythonripper.toolbox.subscription_management as sm
from pythonripper.toolbox.config import ConfigObject, config


async def update_patreon_artists(config: ConfigObject) -> bool:
    obj_artists = sm.CombinedArtistFile(config)
    artists: list[str] = obj_artists.get_list("patreon")
    artists = await patreon.verify_patreon_artist_list(config, artists)

    return await scraper.update_stuff(config, patreon.PatreonAPI, "artists", tag_list=artists)


async def main(config: ConfigObject) -> None:
    await update_patreon_artists(config)


if __name__ == "__main__":
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
