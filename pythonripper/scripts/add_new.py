import asyncio

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.subscription_management as sm


async def add_artists(config: cfg.Config) -> None:
    obj = sm.CombinedArtistFile(config)
    await obj.add_tags()


# async def new_boorutag(config: cfg.Config) -> None:
#     obj = sm.CombinedBooruFile(config)
#     await obj.add_tag_selenium()


# async def new_website_artistfile(config: cfg.Config) -> None:
#     obj = sm.CombinedArtistFile(config)
#     await obj.add_website_selenium(
#         new_website="kusowanka",
#         website_url_format="https://kusowanka.com/artist/{}",
#         regex=r"https://kusowanka.com/([a-zA-Z\d\-\)\(]+/[a-zA-Z\d\-\)\(]+)(?:/)?",
#         space_replace="-",
#         request_breaker_phrase=["404 - Not Found", "Apologies the page you were looking for could not be found"],
#         check_again_if_false=False,
#     )


# async def new_website_boorutags(config: cfg.Config) -> None:
#     obj = sm.CombinedBooruFile(config)
#     await obj.add_website_selenium(
#         new_website="kusowanka",
#         website_url_format="https://kusowanka.com/artist/{}",
#         regex=r"https://kusowanka.com/([a-zA-Z\d\-\)\(]+/[a-zA-Z\d\-\)\(]+)(?:/)?",
#         space_replace="-",
#         request_breaker_phrase=["404 - Not Found", "Apologies the page you were looking for could not be found"],
#         check_again_if_false=False,
#     )


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", False)
    asyncio.run(add_artists(config))
