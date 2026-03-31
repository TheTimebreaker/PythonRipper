import asyncio  # noqa: F401

import toolbox.centralfunctions as cf
import toolbox.config as cfg
import toolbox.subscription_management as sm


async def new_artist(config: cfg.Config) -> None:
    obj = sm.CombinedArtistFile(config)
    await obj.add_tag_selenium()


async def new_boorutag(config: cfg.Config) -> None:
    obj = sm.CombinedBooruFile(config)
    await obj.add_tag_selenium()


async def new_website_artistfile(config: cfg.Config) -> None:
    obj = sm.CombinedArtistFile(config)
    await obj.add_website_selenium(
        new_website="kusowanka",
        website_url_format="https://kusowanka.com/artist/{}",
        regex=r"https://kusowanka.com/([a-zA-Z\d\-\)\(]+/[a-zA-Z\d\-\)\(]+)(?:/)?",
        space_replace="-",
        request_breaker_phrase=["404 - Not Found", "Apologies the page you were looking for could not be found"],
        check_again_if_false=False,
    )


async def new_website_boorutags(config: cfg.Config) -> None:
    obj = sm.CombinedBooruFile(config)
    await obj.add_website_selenium(
        new_website="kusowanka",
        website_url_format="https://kusowanka.com/artist/{}",
        regex=r"https://kusowanka.com/([a-zA-Z\d\-\)\(]+/[a-zA-Z\d\-\)\(]+)(?:/)?",
        space_replace="-",
        request_breaker_phrase=["404 - Not Found", "Apologies the page you were looking for could not be found"],
        check_again_if_false=False,
    )


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", False)

    ### BOTH NEED TO BE TESTED WITH MYPY
    # asyncio.run(new_artist(config))  # noqa: ERA001
    # asyncio.run(new_boorutag(config))  # noqa: ERA001
    # asyncio.run(new_website())  # noqa: ERA001
