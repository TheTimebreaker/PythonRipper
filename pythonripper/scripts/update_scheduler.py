import asyncio
import json
import logging
import time
import traceback
from collections.abc import Callable
from typing import Any

from plyer import notification

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.updater.update_artist_websites
import pythonripper.updater.update_artstation
import pythonripper.updater.update_danbooru
import pythonripper.updater.update_deviantart
import pythonripper.updater.update_gelbooru
import pythonripper.updater.update_hentaifoundry
import pythonripper.updater.update_hypnohub
import pythonripper.updater.update_kusowanka
import pythonripper.updater.update_newgrounds
import pythonripper.updater.update_patreon
import pythonripper.updater.update_pixiv
import pythonripper.updater.update_reddit
import pythonripper.updater.update_rule34paheal
import pythonripper.updater.update_rule34us
import pythonripper.updater.update_rule34xxx
import pythonripper.updater.update_tumblr
import pythonripper.updater.update_yandere


def read_update_scheduler(config: cfg.Config) -> dict[Any, Any]:
    try:
        with open(config.update_scheduler_json_path(), encoding="utf-8") as file:
            last_run: dict[Any, Any] = json.load(file)
        return last_run
    except json.decoder.JSONDecodeError, FileNotFoundError:
        return {}


async def write_update_scheduler(config: cfg.Config, data: dict[Any, Any]) -> None:
    await f.atomic_write(config.update_scheduler_json_path(), json.dumps(data, indent=True))


async def chain(*awaitables: Callable[[Any], Any], config: cfg.Config) -> list[Any]:
    return [await func(config) for func in awaitables]


def unpack_downloader_results(results_packed: list[Any] | tuple[Any, ...]) -> list[Any]:
    results_unpacked = []
    for entry in results_packed:
        if isinstance(entry, list | tuple):
            results_unpacked.extend(unpack_downloader_results(entry))
        else:
            results_unpacked.append(entry)
    return results_unpacked


def repack_downloader_results(results: list[Any] | tuple[Any, ...]) -> list[tuple[Any, ...]]:
    return cf.grouped_iterable(unpack_downloader_results(results), 2)


def windows_notification(title: str = "", message: str = "", app_name: str = "", timeout: int = 10) -> None:
    try:
        notification.notify(title=title, message=message, app_name=app_name, timeout=timeout)
    except ValueError as error:
        logging.debug("[Update scheduler][windows_notification] - %s - %s - %s", title, message, app_name)
        raise ValueError from error


async def update_all(config: cfg.Config) -> dict[str, bool]:
    scheduler: list[tuple[Callable[[Any], Any], int]] = [  # Function, repeat every X days
        # ### higher prio because they are either very important or take long
        (pythonripper.updater.update_reddit.update_reddit_monthly, 0),
        (pythonripper.updater.update_yandere.update_yandere_artists, 28),
        # (updater.update_yandere.update_yandere_tags, 3),
        # ### regular priority
        (pythonripper.updater.update_artstation.update_artstation_artists, 28),
        (pythonripper.updater.update_artist_websites.update_supersatanson, 60),
        (pythonripper.updater.update_artist_websites.update_shellvi, 45),
        (pythonripper.updater.update_artist_websites.update_tangsgallery, 47),
        (pythonripper.updater.update_danbooru.update_danbooru_artists, 28),
        # (updater.update_danbooru.update_danbooru_tags, 4),
        (pythonripper.updater.update_deviantart.update_deviantart_artists, 28),
        (pythonripper.updater.update_deviantart.update_deviantart_favorites, 8),
        (pythonripper.updater.update_gelbooru.update_gelbooru_artists, 28),
        # (updater.update_gelbooru.update_gelbooru_tags, 4),
        (pythonripper.updater.update_hentaifoundry.update_hentaifoundry_artists, 28),
        (pythonripper.updater.update_hypnohub.update_hypnohub_artists, 28),
        # (updater.update_hypnohub.update_hypnohub_tags, 14),
        (pythonripper.updater.update_kusowanka.update_kusowanka_artists, 28),
        # (updater.update_kusowanka.update_kusowanka_tags, 7),
        (pythonripper.updater.update_newgrounds.update_newgrounds_artists, 28),
        (pythonripper.updater.update_newgrounds.update_newgrounds_favorites, 7),
        (pythonripper.updater.update_patreon.update_patreon_artists, 28),
        (pythonripper.updater.update_pixiv.update_pixiv_artists, 28),
        (pythonripper.updater.update_reddit.update_reddit_artists, 28),
        (pythonripper.updater.update_reddit.update_reddit_subs, 6),
        (pythonripper.updater.update_rule34paheal.update_rule34paheal_artists, 28),
        # (updater.update_rule34paheal.update_rule34paheal_tags, 7),
        (pythonripper.updater.update_rule34us.update_rule34us_artists, 28),
        # (updater.update_rule34us.update_rule34us_tags, 7),
        (pythonripper.updater.update_rule34xxx.update_rule34xxx_artists, 28),
        # (updater.update_rule34xxx.update_rule34xxx_tags, 4),
        (pythonripper.updater.update_tumblr.update_tumblr_artists, 28),
    ]

    last_run = read_update_scheduler(config)
    tasks: dict[str, list[Callable[[Any], Any]]] = {}
    success_dict = {}
    for fn, num in scheduler:
        if fn.__name__ not in last_run.keys() or last_run[fn.__name__] + 60 * 60 * 24 * num < time.time():  # If it is already time for the update
            taskname = fn.__name__
            success_dict[taskname] = False

            fn_module = str(fn.__module__)
            if fn_module not in tasks:
                tasks[fn_module] = []
            tasks[fn_module].append(fn)

    chains = [chain(*functions, config=config) for functions in list(tasks.values())]
    for task in asyncio.as_completed(chains):
        try:
            result = await task
            result = repack_downloader_results(result)
            for success_bool, taskname in result:
                success_dict[taskname] = success_bool
                if success_bool is True:
                    last_run[taskname] = time.time()
                    await write_update_scheduler(config, last_run)
        except Exception as error:
            windows_notification(
                title="Update scheduler encountered exception!",
                message=f"Exception encountered while running: {error}. {traceback.format_exc()}",
                app_name="update_scheduler.py",
            )
        else:
            pass  # easygui.msgbox(f'{taskname}: {successBool}')

    print("Finished running... Exiting...")
    return success_dict


if __name__ == "__main__":
    config = cfg.Config()
    cf.init_logger(config, "error", True)
    logging.critical("Update scheduler started!")

    windows_notification(title="Update scheduler started!", message="Started!", app_name="update_scheduler.py")

    try:
        success_dict = asyncio.run(update_all(config))
        assert all(entry is True for entry in success_dict.values())
        windows_notification(title="Update scheduler finished!", message="Finished without problems!", app_name="update_scheduler.py")
        logging.critical("Update scheduler finished without problems!")
    except AssertionError:
        windows_notification(
            title="Update scheduler finished!", message=f"Finished with the following results: {success_dict}!", app_name="update_scheduler.py"
        )
        logging.critical("Update scheduler finished with the following results: %s!", success_dict)
