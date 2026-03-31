import asyncio
import concurrent.futures
import re
import shutil
import time
from pathlib import Path
from typing import Any, Literal

import easygui
import requests
from send2trash import send2trash

from pythonripper.extractor import kusowanka, rule34paheal
import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
from pythonripper.extractor import rule34us


class TestError(Exception):
    pass


@cf.timeout(30)
def get_tags_and_data(
    file: Path,
    obj_kusowanka: kusowanka.KusowankaAPI,
    obj_rule34paheal: rule34paheal.Rule34pahealAPI,
    obj_rule34us: rule34us.Rule34usAPI,
) -> tuple[str | None, str | int | None, list[Any] | None, int | None]:
    """Requests to different websites based on booru filename

    Args:
        filename (_type_): _description_

    Returns:
        (website:str , postId, tags:list, rating:str)
        rating guide:
            0 = general (the only truly non-erotic tier)
            1 = sensitive
            2 = questionable
            3 = explicit

    """
    try:
        if file.name in ("!hashes", "!hashes.csv"):  # ignore these files
            raise TestError

        matched_danbooru = re.match(r"danbooru_([\d]+)_([\w\d]+)", file.name)
        matched_gelbooru = re.match(r"gelbooru_([\d]+)_([\w\d]+)", file.name)
        matched_hypnohub = re.match(r"hypnohub_([\d]+)_([\w\d]+)", file.name)
        matched_kusowanka = re.match(r"kusowanka_([\d]+)", file.name)
        matched_rule34paheal = re.match(r"rule34paheal_([\d]+)_([\w\d]+)", file.name)
        matched_rule34us = re.match(r"rule34us_([\d]+)_([\w\d]+)", file.name)
        matched_rule34xxx = re.match(r"rule34xxx_([\d]+)_([\w\d]+)", file.name)
        matched_yandere = re.match(r"yandere_([\d]+)_([\w\d]+)", file.name)

        data: dict[Any, Any]

        if matched_danbooru:
            post_id = matched_danbooru.group(1)
            url = f"https://danbooru.donmai.us/posts/{post_id}.json"
            res = requests.get(url)
            data = res.json()
            tags = [tag.replace("_", " ") for tag in data["tag_string"].split(" ")]
            website = "danbooru"
            rating = {"g": 0, "s": 1, "q": 2, "e": 3}
            return website, post_id, tags, rating[data["rating"]]

        elif matched_gelbooru:
            post_id = matched_gelbooru.group(1)
            url = f"https://gelbooru.com/index.php?q=index&page=dapi&json=1&s=post&id={post_id}"
            res = requests.get(url)
            data: dict[str, Any] = res.json()["post"][0]  # type: ignore
            tags = [tag.replace("_", " ") for tag in data["tags"].split(" ")]
            website = "gelbooru"
            rating = {"general": 0, "sensitive": 1, "questionable": 2, "explicit": 3}
            return website, post_id, tags, rating[data["rating"]]

        elif matched_hypnohub:
            post_id = matched_hypnohub.group(1)
            url = f"https://hypnohub.net/index.php?q=index&page=dapi&json=1&s=post&id={post_id}"
            res = requests.get(url)
            data: dict = res.json()[0]  # type: ignore
            tags = [tag.replace("_", " ") for tag in data["tags"].split(" ")]
            website = "hypnohub"
            rating = {
                "safe": 0,
                # no sensitive here
                "questionable": 2,
                "explicit": 3,
            }
            return website, post_id, tags, rating[data["rating"]]

        elif matched_kusowanka:
            post_id = int(matched_kusowanka.group(1))
            tags = asyncio.run(obj_kusowanka.__get_post_data_singular(post_id))["tags"]
            website = "kusowanka"
            return website, post_id, tags, None

        elif matched_rule34paheal:
            post_id = matched_rule34paheal.group(1)
            tags = asyncio.run(obj_rule34paheal._get_post_data(post_id))["tags"]
            website = "rule34paheal"
            return website, post_id, tags, None

        elif matched_rule34us:
            post_id = matched_rule34us.group(1)
            tags = asyncio.run(obj_rule34us.__get_post_data_single(post_id))["tags"]
            website = "rule34us"
            return website, post_id, tags, None

        elif matched_rule34xxx:
            post_id = matched_rule34xxx.group(1)
            url = f"https://api.rule34.xxx/index.php?q=index&page=dapi&json=1&s=post&id={post_id}"
            res = requests.get(url)
            data: dict = res.json()[0]  # type: ignore
            tags = [tag.replace("_", " ") for tag in data["tags"].split(" ")]
            website = "rule34xxx"
            rating = {
                "safe": 0,
                # no sensitive here
                "questionable": 2,
                "explicit": 3,
            }
            return website, post_id, tags, rating[data["rating"]]

        elif matched_yandere:
            post_id = matched_yandere.group(1)
            url = f"https://yande.re/post.json?tags=id:{post_id}"
            res = requests.get(url)
            data: dict = res.json()[0]  # type: ignore
            tags = [tag.replace("_", " ") for tag in data["tags"].split(" ")]
            website = "yandere"
            rating = {
                "s": 0,
                # no sensitive here
                "q": 2,
                "e": 3,
            }
            return website, post_id, tags, rating[data["rating"]]

        raise Exception(f"This website is not programmed into me! Filename {file}")
    except KeyError, TestError, requests.exceptions.JSONDecodeError:
        pass
    except requests.exceptions.SSLError:
        time.sleep(5)
    return None, None, None, None


def worker_rmblacklist(
    file: Path,
    blacklist_tags: list[str],
    obj_kusowanka: kusowanka.KusowankaAPI,
    obj_rule34paheal: rule34paheal.Rule34pahealAPI,
    obj_rule34us: rule34us.Rule34usAPI,
) -> tuple[str, str] | Literal[False]:
    website, post_id, tags, _ = get_tags_and_data(file, obj_rule34paheal=obj_rule34paheal, obj_rule34us=obj_rule34us, obj_kusowanka=obj_kusowanka)
    if tags:
        formatted_tags = [tag.replace("&eacute;", "é") for tag in tags]
        if any(blacklistTag in formatted_tags for blacklistTag in blacklist_tags):  # Skips download for blacklisted tags posts
            return website, post_id
    return False


def websitewrapper_rmblacklist(
    files: list[Path],
    website: str,
    blacklist_tags: list[str],
    obj_atl: dict[Any, Any],
    obj_kusowanka: kusowanka.KusowankaAPI,
    obj_rule34paheal: rule34paheal.Rule34pahealAPI,
    obj_rule34us: rule34us.Rule34usAPI,
) -> int:
    lenf = len(files)
    rm_counter = 0
    for i, file in enumerate(files):
        print(f"Currently checking {website} #{i} / {lenf} . Removed #{rm_counter} ...", end="\r")
        result = worker_rmblacklist(
            file=file, blacklist_tags=blacklist_tags, obj_kusowanka=obj_kusowanka, obj_rule34paheal=obj_rule34paheal, obj_rule34us=obj_rule34us
        )
        if result:
            website, post_id = result
            if isinstance(obj_atl[website], type):
                obj_atl[website] = obj_atl[website]()
            send2trash(file)
            obj_atl[website].remove(post_id)
            print(f"Removed {website} {post_id}...")
            rm_counter += 1
    return rm_counter


def filter_files_by_website(files: list[Path]) -> dict[str, list[Path]]:
    return {
        "danbooru": [file for file in files if re.match(r"danbooru_([\d]+)_([\w\d]+)", file.name)],
        "gelbooru": [file for file in files if re.match(r"gelbooru_([\d]+)_([\w\d]+)", file.name)],
        "hypnohub": [file for file in files if re.match(r"hypnohub_([\d]+)_([\w\d]+)", file.name)],
        "kusowanka": [file for file in files if re.match(r"kusowanka_([\d]+)", file.name)],
        "rule34paheal": [file for file in files if re.match(r"rule34paheal_([\d]+)_([\w\d]+)", file.name)],
        "rule34us": [file for file in files if re.match(r"rule34us_([\d]+)_([\w\d]+)", file.name)],
        "rule34xxx": [file for file in files if re.match(r"rule34xxx_([\d]+)_([\w\d]+)", file.name)],
        "yandere": [file for file in files if re.match(r"yandere_([\d]+)_([\w\d]+)", file.name)],
    }


def cleanup_blacklist_tags(directory: Path, start_at_index: int = 0) -> None:
    blacklist_tags = cf.init_blacklist_tags(" ")
    config = cfg.Config()
    obj_kusowanka = kusowanka.KusowankaAPI(config)
    obj_rule34paheal = rule34paheal.Rule34pahealAPI(config)
    obj_rule34us = rule34us.Rule34usAPI(config)
    obj_atl = {
        key: value
        for key, value in (
            ("danbooru", f.SqlDownloadHistory("danbooru", config)),
            ("gelbooru", f.SqlDownloadHistory("gelbooru", config)),
            ("hypnohub", f.SqlDownloadHistory("hypnohub", config)),
            ("kusowanka", f.SqlDownloadHistory("kusowanka", config)),
            ("rule34paheal", f.SqlDownloadHistory("rule34paheal", config)),
            ("rule34us", f.SqlDownloadHistory("rule34us", config)),
            ("rule34xxx", f.SqlDownloadHistory("rule34xxx", config)),
            ("yandere", f.SqlDownloadHistory("yandere", config)),
        )
    }
    all_files = f.list_files(directory)[start_at_index:]
    files = filter_files_by_website(all_files)

    rm_counter = 0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(files.keys())) as pool:
            futures = []
            for website, files_for_website in files.items():  # submits all files
                futures.append(
                    pool.submit(
                        websitewrapper_rmblacklist,
                        files=files_for_website,
                        website=website,
                        blacklist_tags=blacklist_tags,
                        obj_atl=obj_atl,
                        obj_kusowanka=obj_kusowanka,
                        obj_rule34paheal=obj_rule34paheal,
                        obj_rule34us=obj_rule34us,
                    )
                )
            for future in concurrent.futures.as_completed(futures):
                rm_counter += future.result()
    except KeyboardInterrupt:
        print("Ended after KeyboardInterrupt event.")
    except Exception as error:
        raise error
    print(f"Cleanup done for {directory} ! Affected {rm_counter} files, checked {len(all_files)}...")


def worker_movenonexplicit(
    file: Path,
    threshhold: int = 0,
    obj_rule34paheal: rule34paheal.Rule34pahealAPI | None = None,
    obj_rule34us: rule34us.Rule34usAPI | None = None,
) -> tuple[str, str] | Literal[False]:
    # threshhold {0,1,2,3}
    website, post_id, _, explicit = get_tags_and_data(file, obj_rule34paheal=obj_rule34paheal, obj_rule34us=obj_rule34us)
    if explicit is not None and explicit <= threshhold:
        return website, post_id
    return False


def websitewrapper_movenonexplicit(
    files: list[Path],
    website: str,
    threshhold: int,
    obj_rule34paheal: rule34paheal.Rule34pahealAPI,
    obj_rule34us: rule34us.Rule34usAPI,
) -> int:
    lenf = len(files)
    move_counter = 0
    for i, file in enumerate(files):
        print(f"Currently checking {website} #{i} / {lenf} . Moved #{move_counter} ...", end="\r")
        result = worker_movenonexplicit(file=file, threshhold=threshhold, obj_rule34paheal=obj_rule34paheal, obj_rule34us=obj_rule34us)
        if result:
            website, post_id = result
            newdir = file.parent / "_nonexplicit"
            newdir.mkdir(parents=True, exist_ok=True)
            shutil.move(file, newdir / file.name)
            print(f"Moved {website} {post_id}...")
            move_counter += 1
    return move_counter


def move_non_explicit(directory: Path, start_at_index: int = 0, workers: int | None = None) -> None:
    config = cfg.Config()
    obj_rule34paheal = rule34paheal.Rule34pahealAPI(config)
    obj_rule34us = rule34us.Rule34usAPI(config)

    all_files = f.list_files(directory)[start_at_index:]
    files = filter_files_by_website(all_files)

    rm_counter = 0
    try:
        if workers is None:
            workers = len(files.keys())
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = []
            for website, files_per_website in files.items():  # submits all files
                # threshhold means that only higher numbers are kept, rest is moved
                # 0 = general (the only truly non-erotic tier)
                # 1 = sensitive
                # 2 = questionable
                # 3 = explicit
                futures.append(
                    pool.submit(
                        websitewrapper_movenonexplicit,
                        files=files_per_website,
                        website=website,
                        threshhold=2,
                        obj_rule34paheal=obj_rule34paheal,
                        obj_rule34us=obj_rule34us,
                    )
                )

            for future in concurrent.futures.as_completed(futures):
                rm_counter += future.result()
    except KeyboardInterrupt:
        print("Ended after KeyboardInterrupt event.")
    except Exception as error:
        raise error
    print(f"Cleanup done for {directory} ! Affected {rm_counter} files, checked {len(all_files)}...")


def main() -> None:
    config = cfg.Config()
    cf.init_logger(config=config, level="error", log2file=False)

    result = easygui.diropenbox(msg="Select a directory to check on...")
    if not result:
        return
    path = Path(result).resolve()

    choices = ["Cleanup blacklist tags", "Move non-explicit files"]
    result2 = easygui.multchoicebox(msg="Select which operations to do...", choices=choices, preselect=-1)
    if not result2:
        return
    if "Cleanup blacklist tags" in result2:
        cleanup_blacklist_tags(path)
    if "Move non-explicit files" in result2:
        move_non_explicit(path)


if __name__ == "__main__":
    main()
