import asyncio
import json
import logging
import time
from collections.abc import Callable, Coroutine
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


async def save_success(config: cfg.Config, last_run: dict[Any, Any], func_name: str, completed_at: float, write_lock: asyncio.Lock) -> None:
    async with write_lock:
        last_run[func_name] = completed_at
        await write_update_scheduler(config, last_run)


async def run_group(
    group: dict[str, Callable[[cfg.Config], Coroutine[None, None, bool]]], config: cfg.Config, last_run: dict[Any, Any], write_lock: asyncio.Lock
) -> dict[str, bool]:
    results = {}

    for func_name, func in group.items():
        res = await func(config)
        results[func_name] = res

        if res is True:
            completed_at = time.time()
            save_task = asyncio.create_task(save_success(config, last_run, func_name, completed_at, write_lock))
            try:
                await asyncio.shield(save_task)
            except asyncio.CancelledError:
                await save_task
                raise

    return results


async def run_all_groups(
    groups: dict[str, dict[str, Callable[[cfg.Config], Coroutine[None, None, bool]]]], config: cfg.Config, last_run: dict[Any, Any]
) -> dict[str, bool]:

    write_lock = asyncio.Lock()
    group_results = await asyncio.gather(*(run_group(group, config, last_run, write_lock) for group in groups.values()))
    return {func_name: result for group_result in group_results for func_name, result in group_result.items()}


def windows_notification(title: str = "", message: str = "", app_name: str = "", timeout: int = 10) -> None:
    try:
        notification.notify(title=title, message=message, app_name=app_name, timeout=timeout)
    except ValueError as error:
        logging.debug("[Update scheduler][windows_notification] - %s - %s - %s", title, message, app_name)
        raise ValueError from error


async def update_all(config: cfg.Config) -> dict[str, bool]:
    scheduler: list[tuple[Callable[[Any], Any], int]] = [
        (pythonripper.updater.update_artstation.update_artstation_artists, 28),
        (pythonripper.updater.update_artist_websites.update_supersatanson, 60),
        (pythonripper.updater.update_artist_websites.update_akairiot, 60),
        (pythonripper.updater.update_artist_websites.update_shellvi, 60),
        (pythonripper.updater.update_artist_websites.update_tangsgallery, 60),
        (pythonripper.updater.update_danbooru.update_danbooru_artists, 28),
        (pythonripper.updater.update_danbooru.update_danbooru_tags, 4),
        (pythonripper.updater.update_deviantart.update_deviantart_artists, 28),
        (pythonripper.updater.update_deviantart.update_deviantart_favorites, 8),
        (pythonripper.updater.update_gelbooru.update_gelbooru_artists, 28),
        (pythonripper.updater.update_gelbooru.update_gelbooru_tags, 4),
        (pythonripper.updater.update_hentaifoundry.update_hentaifoundry_artists, 28),
        (pythonripper.updater.update_hypnohub.update_hypnohub_artists, 28),
        (pythonripper.updater.update_hypnohub.update_hypnohub_tags, 14),
        (pythonripper.updater.update_kusowanka.update_kusowanka_artists, 28),
        (pythonripper.updater.update_kusowanka.update_kusowanka_tags, 7),
        (pythonripper.updater.update_newgrounds.update_newgrounds_artists, 28),
        (pythonripper.updater.update_newgrounds.update_newgrounds_favorites, 7),
        (pythonripper.updater.update_patreon.update_patreon_artists, 28),
        (pythonripper.updater.update_pixiv.update_pixiv_artists, 28),
        (pythonripper.updater.update_rule34paheal.update_rule34paheal_artists, 28),
        (pythonripper.updater.update_rule34paheal.update_rule34paheal_tags, 7),
        (pythonripper.updater.update_rule34us.update_rule34us_artists, 28),
        (pythonripper.updater.update_rule34us.update_rule34us_tags, 7),
        (pythonripper.updater.update_rule34xxx.update_rule34xxx_artists, 28),
        (pythonripper.updater.update_rule34xxx.update_rule34xxx_tags, 4),
        (pythonripper.updater.update_tumblr.update_tumblr_artists, 28),
        (pythonripper.updater.update_yandere.update_yandere_artists, 28),
        (pythonripper.updater.update_yandere.update_yandere_tags, 3),
    ]

    last_run = read_update_scheduler(config)
    tasks: dict[str, dict[str, Callable[[Any], Any]]] = {}
    for fn, num in scheduler:
        func_name = fn.__name__
        if func_name not in last_run.keys() or last_run[func_name] + 60 * 60 * 24 * num < time.time():  # If it is already time for the update
            fn_module = str(fn.__module__)
            if fn_module not in tasks:
                tasks[fn_module] = {}
            tasks[fn_module][func_name] = fn

    results = await run_all_groups(tasks, config, last_run)
    print("Finished running... Exiting...")
    return results


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
