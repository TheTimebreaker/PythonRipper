"""Central functions that can't be stored in main due to circular dependencies"""

import datetime
import functools
import logging
import multiprocessing.pool
import random
import shutil
import string
import time
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests
import wget
from selenium.webdriver.remote.webdriver import WebDriver

import pythonripper.toolbox.config as cfg


def timeout(max_timeout_seconds: int) -> Callable[[Any], Any]:
    """Timeout decorator, parameter in seconds. Usage as decorator:
    e.g. @timeout(5)"""

    def timeout_decorator(item: Any) -> Callable[[Any], Any]:
        """Wrap the original function."""

        @functools.wraps(item)
        def func_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Closure for function."""
            pool = multiprocessing.pool.ThreadPool(processes=1)
            async_result = pool.apply_async(item, args, kwargs)
            # raises a TimeoutError if execution exceeds max_timeout
            return async_result.get(max_timeout_seconds)

        return func_wrapper

    return timeout_decorator


def progress_bar(progress: int, total: int, title: str = "Progress", newline: bool = True, return_as_string: bool = False) -> bool | str:
    percentage = progress / float(total) * 100
    percentage_text = f"{percentage:.2f}".rjust(6, " ")
    bar_perc = percentage / 2
    bar_text = "█" * int(bar_perc) + "-" * (50 - int(bar_perc))

    msg = f'\r|{bar_text}| {str(progress).rjust(len(str(total)), "_")}/{str(total).rjust(len(str(total)), "_")}={percentage_text}% - {title}'
    if return_as_string:
        return msg
    else:
        print(msg)
        if newline and percentage == 100:
            print("")
    return True


def progress_bar_timed(
    lasttime: float, timing: float | int, progress: int, total: int, title: str = "Progress", newline: bool = True, return_as_string: bool = False
) -> bool | str:
    now = time.time()
    if progress <= 1 or progress >= total or (now - lasttime) > timing:
        return progress_bar(progress, total, title, newline, return_as_string)
    else:
        return False


def id_generator(size: int = 6) -> str:
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(size))


def asynctimeoutseconds() -> int:
    return 60  # seconds


def multi_character_replace(string_input: str, translate: dict[str, str]) -> str:
    for what, by in translate.items():
        string_input = string_input.replace(what, by)
    return string_input


def init_blacklist_tags(ignore_symbol: str = "//") -> list[str]:
    blpath = cfg.Config().blacklist_tags_path()
    backlist_tags = []
    with open(blpath, encoding="utf-16") as f:
        for tag in f.read().split("\n"):
            if str(tag).startswith(ignore_symbol):
                continue
            backlist_tags.append(tag)
    return backlist_tags


def get_digits(integer: int) -> int:
    return len(str(integer))


def init_logger(config: cfg.Config, level: str, log2file: bool) -> None:
    level = level.lower()
    match level:  # Matches the level argument to the words logging actually understands :)
        case "debug":
            level = "DEBUG"
        case "info":
            level = "INFO"
        case "warning":
            level = "WARNING"
        case "error":
            level = "ERROR"
        case "critical":
            level = "CRITICAL"

        case _:
            level = "DEBUG"

    msg_format = "[%(asctime)s][%(levelname)s]%(message)s"

    if log2file:
        print(f"Logs will be logged into: {config.errorpath()}")
        logging.basicConfig(
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(config.errorpath(), encoding="utf-16"),
            ],
            level=level,
            format=msg_format,
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        logging.basicConfig(
            handlers=[
                logging.StreamHandler(),
            ],
            level=level,
            format=msg_format,
        )

    logging.critical(datetime.datetime.strftime(datetime.datetime.now(), format="%Y-%m-%d %H:%M:%S"))


def init_selenium(headless: bool = False) -> WebDriver:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    chromedriver_main = cfg.Config().chromedriver_path()

    def chromeversion_download() -> tuple[Path, Path]:
        """Checks latest Chrome-for-testing and Chromedriver version, downloads them (if needed)
        and returns the paths to chrome.exe and chromedriver.exe

                Returns:
                    tuple(path/to/latest/chrome.exe, path/to/latest/chromedriver.exe)
        """
        latest_chrome_version = requests.get("https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE", timeout=60).text

        latest_chrome_download_url = f"https://storage.googleapis.com/chrome-for-testing-public/{latest_chrome_version}/win64/chrome-win64.zip"
        latest_chrome_path = chromedriver_main / f"{latest_chrome_version} chrome-win64"
        latest_chrome_path_tmp = latest_chrome_path.with_name(latest_chrome_path.name + "-temp")
        latest_chrome_path_zip = latest_chrome_path.with_name(latest_chrome_path.name + ".zip")

        latest_chromedriver_download_url = (
            f"https://storage.googleapis.com/chrome-for-testing-public/{latest_chrome_version}/win64/chromedriver-win64.zip"
        )
        latest_chromedriver_path = chromedriver_main.joinpath(f"{latest_chrome_version} chromedriver-win64")
        latest_chromedriver_path_tmp = latest_chromedriver_path.with_name(latest_chromedriver_path.name + "-temp")
        latest_chromedriver_path_zip = latest_chromedriver_path.with_name(latest_chromedriver_path.name + ".zip")

        if not latest_chrome_path.is_dir():
            wget.download(url=latest_chrome_download_url, out=str(latest_chrome_path_zip))

            with zipfile.ZipFile(latest_chrome_path_zip, "r") as zip_ref:
                zip_ref.extractall(path=latest_chrome_path_tmp)  # you can specify the destination folder path here
            latest_chrome_path_zip.unlink()
            shutil.move(latest_chrome_path_tmp / "chrome-win64", latest_chrome_path)
            latest_chrome_path_tmp.rmdir()

        if not latest_chromedriver_path.is_dir():
            wget.download(url=latest_chromedriver_download_url, out=str(latest_chromedriver_path_zip))

            with zipfile.ZipFile(latest_chromedriver_path_zip, "r") as zip_ref:
                zip_ref.extractall(path=latest_chromedriver_path_tmp)  # you can specify the destination folder path here
            latest_chromedriver_path_zip.unlink()
            shutil.move(latest_chromedriver_path_tmp / "chromedriver-win64", latest_chromedriver_path)
            latest_chromedriver_path_tmp.rmdir()

        return latest_chrome_path.joinpath("chrome.exe"), latest_chromedriver_path.joinpath("chromedriver.exe")

    chrome_path, chromedriver_path = chromeversion_download()
    options = Options()
    options.binary_location = str(chrome_path.resolve())
    if headless:
        options.add_argument("--headless")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    service = Service(executable_path=str(chromedriver_path))

    driver: WebDriver = webdriver.Chrome(service=service, options=options)
    print("ublock lite: https://chromewebstore.google.com/detail/ublock-origin-lite/ddkjiahejlhfcafbddmgiahcphecmpfh")
    print("Tampermonkey: https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo")
    return driver


def grouped_iterable(iterable: list[Any], n: int) -> list[tuple[Any, ...]]:
    "s -> (s0,s1,s2,...sn-1), (sn,sn+1,sn+2,...s2n-1), (s2n,s2n+1,s2n+2,...s3n-1), ..."
    return list(zip(*[iter(iterable)] * n, strict=True))


class ExtractorExitError(Exception):
    """Exception that signals the extractor to exit current tag without stopping execution of website (e.g. if tag was deleted)."""


class ExtractorStopError(Exception):
    """Exception that signals the extractor to exit and fully stop operating (e.g. when hitting a rate limit)."""


class InterruptError(Exception):
    """Exception for when you want to catch another exception in one line in one function,
    because catching the error outside said function would lead to unexpected catches."""


def get_full_class_name(obj: Exception) -> str:
    module = obj.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return obj.__class__.__name__
    return module + "." + obj.__class__.__name__
