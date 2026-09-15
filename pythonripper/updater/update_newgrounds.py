import asyncio
import logging
import traceback

import aiofiles
import httpx

import pythonripper.extractor.newgrounds as newgrounds
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


async def update_newgrounds_artists(config: cfg.Config) -> bool:
    return await scraper.update_stuff(config, newgrounds.NewgroundsAPI, "artists")


async def update_newgrounds_favorites(config: cfg.Config) -> bool | tuple[bool, str]:
    print("Updating local copy of newgrounds favorites.")
    update_type = "favorites"

    favorites = []
    async with aiofiles.open(config.newgrounds_favs_path(), newline="") as file:
        contents = await file.read()
        for i, favorite in enumerate(contents.split("\n")):
            if i <= 1:
                continue
            favorites.append(favorite)

    obj = newgrounds.NewgroundsAPI(config)
    if not await obj.init():
        return False

    full_success = True
    for i, fav in enumerate(favorites):
        print(f"{i+1}/{len(favorites)} - {fav} - newgrounds-favorites")
        download_folder = config.dpath() / "newgrounds-favorites" / f.verify_filename(fav)
        download_folder.mkdir(parents=True, exist_ok=True)

        try:
            success = await obj.download_tag(fav, download_folder, True, custom_mode="newgrounds", endpoint="art", fetch_favorites=True)
        except cf.ExtractorExitError as error:
            tb = traceback.TracebackException.from_exception(error)
            logging.error(
                "[%s-%s-UPDATER] - Extractor signaled to exit current tag. Message : %s ",
                obj.ME.upper(),
                update_type.upper(),
                "".join(tb.format()),
            )
            success = False
        except cf.ExtractorStopError as error:
            tb = traceback.TracebackException.from_exception(error)
            logging.error(
                "[%s-%s-UPDATER] - Extractor was signaled to stop execution. Message : %s",
                obj.ME.upper(),
                update_type.upper(),
                "".join(tb.format()),
            )
            return False
        except httpx.HTTPStatusError as error:
            tb = traceback.TracebackException.from_exception(error)
            logging.error(
                "[%s-%s-UPDATER] - Extractor encountered a 4xx or 5xx HTTP response. Message : %s",
                obj.ME.upper(),
                update_type.upper(),
                "".join(tb.format()),
            )
            return False
        if not success:
            full_success = False
            logging.error(
                "[%s-%s-UPDATER] - Some issue occurred that prevented some images by fav %s being correctly downloaded.",
                obj.ME.upper(),
                update_type.upper(),
                fav,
            )
        print("=" * 50)

    return full_success


async def main(config: cfg.Config) -> None:
    await update_newgrounds_artists(config)
    await update_newgrounds_favorites(config)


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    asyncio.run(main(config))
