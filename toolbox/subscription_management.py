import json
import logging
import re
import sys
import webbrowser
from collections.abc import Generator, KeysView
from pathlib import Path
from typing import Any, ClassVar, NotRequired, TypedDict

import easygui
import requests
from selenium.webdriver.remote.webdriver import WebDriver

import toolbox.centralfunctions as cf
import toolbox.config as cfg
import toolbox.files as f


class WebsiteInfo(TypedDict):
    url: str | list[str]
    regex: str
    space_replace: NotRequired[str]
    google: bool


class CombinedFile:
    space_default = "_"
    websiteinfo: ClassVar[dict[str, WebsiteInfo]] = {
        "animepictures": {
            "url": "https://anime-pictures.net/posts?search_tag={tagname}&lang=en",
            "regex": r"https://(?:www\.)?anime\-pictures\.net/posts\?(?:.+)?search_tag=([^/&\?]+)",
            "google": True,
        },
        "artstation": {
            "url": "https://artstation.com/{tagname}",
            "regex": r"https://(?:www\.)?artstation\.com/([^/&\?]+)",
            "google": True,
        },
        "danbooru": {
            "url": "https://danbooru.donmai.us/posts?tags={tagname}",
            "regex": r"https://(?:www\.)?danbooru\.donmai\.us/posts\?(?:.+)?tags=([^/&\?]+)",
            "google": False,
        },
        "deviantart": {
            "url": "https://deviantart.com/{tagname}",
            "regex": r"https://(?:www\.)?deviantart\.com/([^/&\?]+)",
            "google": True,
        },
        "gelbooru": {
            "url": "https://gelbooru.com/index.php?page=post&s=list&tags={tagname}",
            "regex": r"https://(?:www\.)?gelbooru\.com/index\.php\?(?:.+)?tags=([^/&\?]+)",
            "google": False,
        },
        "hentaifoundry": {
            "url": "https://hentai-foundry.com/user/{tagname}?enterAgree=1",
            "regex": r"https://(?:www\.)?hentai-foundry\.com/(?:pictures/)?user/([^/&\?]+)",
            "google": False,
        },
        "hypnohub": {
            "url": "https://hypnohub.net/index.php?page=post&s=list&tags={tagname}",
            "regex": r"https://(?:www\.)?hypnohub\.net/index\.php\?(?:.+)?tags=([^/&\?]+)",
            "google": False,
        },
        "newgrounds": {
            "url": "https://{tagname}.newgrounds.com",
            "regex": r"https://(?:www\.)?([^/&\?]+)\.newgrounds\.com",
            "google": False,
        },
        "kusowanka": {
            "url": [
                "https://kusowanka.com/artist/{tagname}",
                "https://kusowanka.com/character/{tagname}",
                "https://kusowanka.com/metadata/{tagname}",
                "https://kusowanka.com/parody/{tagname}",
                "https://kusowanka.com/tag/{tagname}",
            ],
            "regex": r"https://(?:www\.)?kusowanka\.com/(artist|character|metadata|parody|tag)/([^/&\?]+)",
            "google": False,
        },
        "patreon": {
            "url": "https://patreon.com/{tagname}",
            "regex": r"https://(?:www\.)?patreon\.com/([^/&\?]+)",
            "google": True,
        },
        "pixiv": {
            "url": "https://www.pixiv.net/en/users/{tagname}",
            "regex": r"https://(?:www\.)?pixiv\.net/en/users/(\d+)",
            "google": True,
        },
        "reddit": {
            "url": [
                "https://www.reddit.com/r/{tagname}",
                "https://www.reddit.com/u/{tagname}",
                "https://www.reddit.com/user/{tagname}",
            ],
            "regex": r"https://(?:www\.)?reddit\.com/(r|u|user)/([^/&\?]+)",
            "google": False,
        },
        "rule34paheal": {
            "url": "https://rule34.paheal.net/post/list/{tagname}/1",
            "regex": r"https://(?:www\.)?rule34\.paheal\.net/post/list/([^/&\?]+)",
            "google": False,
        },
        "rule34us": {
            "url": "https://rule34.us/index.php?r=posts/index&q={tagname}",
            "regex": r"https://(?:www\.)?rule34\.us/index\.php\?(?:.+)?q=([^/&\?]+)",
            "google": False,
        },
        "rule34xxx": {
            "url": "https://rule34.xxx/index.php?page=post&s=list&tags={tagname}",
            "regex": r"https://(?:www\.)?rule34\.xxx/index\.php\?(?:.+)?tags=([^/&\?]+)",
            "google": False,
        },
        "tumblr": {
            "url": "https://tumblr.com/{tagname}",
            "regex": r"https://(?:www\.)?tumblr\.com/([^/&\?]+)",
            "google": False,
        },
        "yandere": {
            "url": "https://yande.re/post?tags={tagname}",
            "regex": r"https://(?:www\.)?yande\.re(?:.+)tags=([^/&\?]+)",
            "google": False,
        },
    }

    websites: ClassVar[list[str]]
    path: Path
    tag_type: str = ""

    def __init__(self, config: cfg.Config) -> None:
        self.data = self.read()
        self.config = config
        self.check_keys()

    def read(self) -> dict[Any, Any]:
        with open(self.path, encoding="utf-8") as file:
            result: dict[Any, Any] = json.load(file)
            return result

    def sort(self) -> None:
        def recursive_sort(d: dict[Any, Any]) -> dict[Any, Any]:
            temp: dict[Any, dict[Any, Any] | list[Any] | bool] = {}
            for key, value in d.items():
                if isinstance(value, dict):
                    temp[key] = recursive_sort(value)
                elif isinstance(value, list) and len(value) == 0:
                    temp[key] = False
                elif isinstance(value, list) and len(value) == 1:
                    temp[key] = value[0]
                elif isinstance(value, list):
                    temp[key] = sorted(list(dict.fromkeys(value)), key=lambda k: str(k).lower())
                else:
                    temp[key] = value
            return dict(sorted(temp.items(), key=lambda k: str(k[0]).lower()))

        # Cleanup
        for sort_tag in self.data:
            trans = {
                "_": " ",
                "%20": " ",
                "%28": "(",
                "%29": ")",
            }
            for website in self.data[sort_tag]:
                if isinstance(self.data[sort_tag][website], str):
                    self.data[sort_tag][website] = cf.multi_character_replace(str(self.data[sort_tag][website]).lower(), trans)
                elif isinstance(self.data[sort_tag][website], list) and all(isinstance(test, str) for test in self.data[sort_tag][website]):
                    self.data[sort_tag][website] = [cf.multi_character_replace(str(text).lower(), trans) for text in self.data[sort_tag][website]]

        # Recursively sorts dictionary
        self.data = recursive_sort(self.data)

    async def write(self) -> None:
        self.sort()
        await f.atomic_write(filepath=self.path, data=json.dumps(self.data, indent=4), encoding="utf-8")

    async def add_tag(self, new_tag: str | None = None) -> None:
        if not new_tag:
            result = easygui.enterbox(msg=f"Please enter the {self.tag_type} which you wanna add.", title=f"Enter {self.tag_type}")
            if not result:
                return
            elif result in str(self.data):
                pw = cf.id_generator(6)
                print(
                    f'The given {self.tag_type} "{result}" was found in your subscribed list. If this is not the case, please enter the following code:'
                )
                if input(f"Enter {pw} :") != pw:  # noqa: ASYNC250
                    return
            new_tag = str(result)

        new_tag_data = {key: None for key in self.websiteinfo.keys()}
        print(new_tag_data)

        # driver = cf.init_selenium(False)

    def get_list(self, website: str) -> list[Any]:
        """Returns sorted list of all entries from a given website."""
        taglist = []
        for name, name_data in self.data.items():
            for website_name, is_there in name_data.items():
                if website_name == website and is_there:
                    if isinstance(is_there, str | int):
                        if is_there in taglist:
                            logging.warning(
                                "[%s] The tag \x1b[3m%s\x1b[0m from sorting tag \x1b[3m%s\x1b[0m appears multiple times in your json file!",
                                website_name,
                                is_there,
                                name,
                            )
                        taglist.append(is_there)
                    elif isinstance(is_there, list):
                        for sublink in is_there:
                            if sublink in taglist:
                                logging.warning(
                                    "[%s] The tag \x1b[3m%s\x1b[0m from sorting tag \x1b[3m%s\x1b[0m appears multiple times in your json file!",
                                    website_name,
                                    sublink,
                                    name,
                                )
                            taglist.append(sublink)

        return sorted([str(x).lower() for x in taglist])

    def get_all(self) -> dict[Any, Any]:
        """Returns sorted list of all entries from all websites."""
        taglist: dict[str, dict[str | int, str | bool]] = {}
        for name, name_data in self.data.items():
            taglist[name] = {}
            for _, is_there in name_data.items():
                if is_there:
                    if isinstance(is_there, str | int):
                        taglist[name][is_there] = True
                    elif isinstance(is_there, list):
                        for sublink in is_there:
                            taglist[name][sublink] = True

        return {name: list(value.keys()) for name, value in taglist.items()}

    def check_keys(self) -> None:
        for tag, tag_data in self.data.items():
            for key in self.websites:
                if key not in tag_data.keys():
                    print(f"[{tag}][{key}] - Website key missing.")
        for site in self.websites:
            self.get_list(site)


class CombinedArtistFile(CombinedFile):
    path: Path
    websites: ClassVar[list[str]] = [
        "artstation",
        "asmhentai",
        "danbooru",
        "doujinscom",
        "deviantart",
        "gelbooru",
        "hentaienvy",
        "hentaiera",
        "hentaiforce",
        "hentaifoundry",
        "hentairead",
        "hypnohub",
        "kusowanka",
        "newgrounds",
        "nhentainet",
        "patreon",
        "pixiv",
        "reddit",
        "rule34paheal",
        "rule34us",
        "rule34xxx",
        "rule34xyz",
        "tumblr",
        "twitter",
        "yandere",
    ]
    tag_type = "artist"

    def __init__(self, config: cfg.Config) -> None:
        self.path = config.artists_tags_path()
        super().__init__(config)


class CombinedBooruFile(CombinedFile):
    path: Path
    websites: ClassVar[list[str]] = ["danbooru", "gelbooru", "hypnohub", "kusowanka", "rule34paheal", "rule34us", "rule34xxx", "rule34xyz", "yandere"]
    tag_type = "booru tag"

    def __init__(self, config: cfg.Config) -> None:
        self.path = config.booru_tags_path()
        super().__init__(config)
