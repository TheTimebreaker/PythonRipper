import asyncio

import pythonripper.extractor.hentaifoundry as hentaifoundry
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config import ConfigObject


async def update_hentaifoundry_artists(config: ConfigObject) -> bool:
    return await scraper.update_stuff(config, hentaifoundry.HentaiFoundry, "artists")


async def main(config: ConfigObject) -> None:
    await update_hentaifoundry_artists(config)


if __name__ == "__main__":
    config = ConfigObject()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
