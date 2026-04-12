import asyncio
import json
import logging
import re
import urllib.parse
from collections.abc import Iterable
from pathlib import Path
from typing import Any, ClassVar, NotRequired, TypedDict, cast

from selenium.common.exceptions import NoSuchWindowException, WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.config as cfg
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.extractor import (
    animepictures,
    artstation,
    danbooru,
    deviantart,
    gelbooru,
    hentaifoundry,
    hypnohub,
    kusowanka,
    newgrounds,
    patreon,
    pixiv,
    reddit,
    rule34paheal,
    rule34us,
    rule34xxx,
    tumblr,
    yandere,
)

STOP = object()


class WebsiteInfo(TypedDict):
    object: type[scraper.TaggableScraper]
    object_active: NotRequired[scraper.TaggableScraper]


class CombinedFile:
    space_default = "_"
    websiteinfo: ClassVar[dict[str, WebsiteInfo]] = {
        "animepictures": {"object": animepictures.Animepictures},
        "artstation": {"object": artstation.ArtstationAPI},
        "danbooru": {"object": danbooru.DanbooruAPI},
        "deviantart": {"object": deviantart.DeviantartAPI},
        "gelbooru": {"object": gelbooru.GelbooruAPI},
        "hentaifoundry": {"object": hentaifoundry.HentaiFoundry},
        "hypnohub": {"object": hypnohub.HypnohubAPI},
        "newgrounds": {"object": newgrounds.NewgroundsAPI},
        "kusowanka": {"object": kusowanka.KusowankaAPI},
        "patreon": {"object": patreon.PatreonAPI},
        "pixiv-artists": {"object": pixiv.PixivArtistAPI},
        "pixiv-tags": {"object": pixiv.PixivTagAPI},
        "reddit": {"object": reddit.RedditAPI},
        "rule34paheal": {"object": rule34paheal.Rule34pahealAPI},
        "rule34us": {"object": rule34us.Rule34usAPI},
        "rule34xxx": {"object": rule34xxx.Rule34xxxAPI},
        "tumblr": {"object": tumblr.TumblrAPI},
        "yandere": {"object": yandere.YandereAPI},
    }

    websites: ClassVar[list[str]]
    path: Path
    tag_type: str = ""
    encoding = "utf-8"

    google_url = "https://www.google.com/search?q={query}"
    google_space_replace = "+"

    def __init__(self, config: cfg.Config) -> None:
        self.data = self.read()
        self.config = config
        self.check_keys()

    def read(self) -> dict[Any, Any]:
        with open(self.path, encoding=self.encoding) as file:
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
                    temp[key] = sorted(list(dict.fromkeys(value)), key=lambda k: str(k))
                else:
                    temp[key] = value
            return dict(sorted(temp.items(), key=lambda k: str(k[0])))

        # Cleanup
        for sort_tag in self.data:
            for website in self.data[sort_tag]:
                if isinstance(self.data[sort_tag][website], str):
                    self.data[sort_tag][website] = cf.unquote_tagnames(str(self.data[sort_tag][website]))
                elif isinstance(self.data[sort_tag][website], list) and all(isinstance(test, str) for test in self.data[sort_tag][website]):
                    self.data[sort_tag][website] = [cf.unquote_tagnames(str(text)) for text in self.data[sort_tag][website]]

        # Recursively sorts dictionary
        self.data = recursive_sort(self.data)

    async def write(self) -> None:
        self.sort()
        await f.atomic_write(filepath=self.path, data=self.data, encoding=self.encoding)

    async def _add_activate_dict(self, config: cfg.Config, choice: str | None = None) -> None:
        async def task(key: str, obj_type: type[scraper.TaggableScraper]) -> None:
            obj = obj_type(config)
            if not await obj.init():
                raise Exception("Could not initialize all scraper objects: %s failed.", key)
            self.websiteinfo[key]["object_active"] = obj

        tasks = []
        for key in self.websites:
            if not choice or choice == key:
                tasks.append(asyncio.create_task(task(key, self.websiteinfo[key]["object"])))
        await asyncio.gather(*tasks)

    def _add_ensure_fallback_tab(self, driver: WebDriver, fallback_url: str = "about:blank") -> str:
        """
        Make sure there is a dedicated fallback tab and return its window handle.

        This tab stays open permanently so the browser session does not end up with
        zero meaningful tabs during cleanup.
        """
        if not driver.window_handles:
            raise RuntimeError("Driver has no open windows.")

        # Reuse the current tab as fallback if possible.
        fallback_handle = driver.current_window_handle
        driver.get(fallback_url)
        return fallback_handle

    def _add_open_urls_in_new_tabs(self, driver: WebDriver, urls: Iterable[str], fallback_handle: str) -> list[str]:
        """
        Open each URL in its own new tab and return the created tab handles.
        """
        created_handles: list[str] = []

        for url in urls:
            driver.switch_to.window(fallback_handle)
            driver.switch_to.new_window("tab")
            new_handle = driver.current_window_handle
            created_handles.append(new_handle)

            try:
                driver.get(url)
            except WebDriverException as exc:
                print(f"Failed to open {url!r}: {exc}")
                # If opening fails, close that tab again.
                try:
                    driver.close()
                except Exception:
                    pass

                # Switch back to fallback so the driver stays in a sane state.
                driver.switch_to.window(fallback_handle)
                created_handles.remove(new_handle)

        return created_handles

    def _add_close_non_fallback_tabs(self, driver: WebDriver, fallback_handle: str) -> None:
        """
        Close every tab except the fallback tab.
        """
        for handle in list(driver.window_handles):
            if handle == fallback_handle:
                continue

            try:
                driver.switch_to.window(handle)
                driver.close()
            except NoSuchWindowException:
                continue
            except WebDriverException as exc:
                print(f"Could not close tab {handle!r}: {exc}")

        driver.switch_to.window(fallback_handle)

    def _add_userconfirm_console(self, name: str) -> None:
        """
        Simple console-based confirmation.
        The human can manually close bad tabs, then press Enter.
        """
        input(f"\nReview tabs for {name!r}.\n Close the bad tabs manually, keep the good ones open,\n then press Enter to continue...")

    def _add_userconfirm_popup(self, name: str) -> None:
        """
        Optional Tkinter popup confirmation.
        """
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            title="Review URLs",
            message=(f"Review tabs for {name!r}.\n\n Close the bad tabs manually, keep the good ones open,\n then click OK."),
        )
        root.destroy()

    async def _add_get_tag_urls(self, tagname: str, website: str | None = None, dont_add_homepage: bool = False) -> list[str]:
        async def task(obj: scraper.TaggableScraper) -> None:
            urls_to_format = []
            if isinstance(obj.URL_TAG, str):
                urls_to_format = [obj.URL_TAG]
            else:
                urls_to_format = [*obj.URL_TAG]

            found_some = False
            for url_to_format in urls_to_format:
                this_url = url_to_format.format(tagname=obj.format_tagname(tagname))
                this_tagname = tagname

                try:
                    x = await obj.does_this_exist(this_tagname)
                    if x:
                        result.add(this_url)
                        found_some = True
                    else:
                        continue
                except json.decoder.JSONDecodeError, ConnectionAbortedError, ConnectionRefusedError, cf.ExtractorExitError, cf.ExtractorStopError:
                    pass

            if found_some is False:
                if obj.IS_GOOGLE_SEARCHABLE is True:
                    result.add(self.google_url.format(query=(f"{tagname} {obj.ME.lower()}").replace(" ", self.google_space_replace)))
                if dont_add_homepage is False:
                    result.add(obj.HOMEPAGE)

        result: set[str] = set()
        tasks: list[asyncio.Task[None]] = []
        for key in self.websites:
            if website is None or website == key:
                obj = self.websiteinfo[key]["object_active"]
                tasks.append(asyncio.create_task(task(obj)))
        await asyncio.gather(*tasks)
        return list(result)

    def _add_get_confirmed_urls(self, driver: WebDriver, fallback_handle: str) -> list[str]:
        """
        Return the URLs of all currently open tabs except the fallback tab.
        """
        confirmed_urls: list[str] = []

        # Snapshot because window_handles may change if the browser is touched.
        for handle in list(driver.window_handles):
            if handle == fallback_handle:
                continue

            try:
                driver.switch_to.window(handle)
                url = driver.current_url
                confirmed_urls.append(url)
            except NoSuchWindowException:
                # User may have closed it between reading handles and switching.
                continue
            except WebDriverException as exc:
                print(f"Could not read URL from tab {handle!r}: {exc}")

        # Restore focus to fallback at the end.
        driver.switch_to.window(fallback_handle)
        return confirmed_urls

    async def process_urls(self, new_tag: str, url_list: list[str], choice: str | None = None) -> None:
        if new_tag in self.data:
            new_tag_obj = self.data[new_tag]
        else:
            new_tag_obj = {}
        for key in self.websites:
            if key not in new_tag_obj:
                new_tag_obj[key] = []

        for url in url_list:
            url = urllib.parse.unquote(url)
            for key in self.websites:
                if not choice or choice == key:
                    obj = self.websiteinfo[key]["object_active"]
                    try:
                        matched = re.match(obj.TAG_PATTERN, url)
                        if not matched:
                            raise AttributeError
                        tag_formatted = matched.group(1)
                        tag = tag_formatted.replace(obj.SPACE_REPLACE, " ")
                        while tag.startswith((" ", "+")):
                            tag = tag[1:]
                        while tag.endswith((" ", "+")):
                            tag = tag[:-1]

                        if re.match(r"^(?:\s?[A-Za-z]\s)+$", tag):
                            raise ValueError("Tag %s was detected with spaces from url %s and pattern %s", tag, url, obj.TAG_PATTERN)
                        new_tag_obj[key].append(tag)
                        break
                    except AttributeError:
                        continue
            else:
                print(f"Could not verify link {url} .")
        self.data[new_tag] = new_tag_obj
        await self.write()

    async def worker_producer(
        self, artists: list[tuple[int, str]], q: asyncio.Queue[tuple[int, str, set[str]] | object], choice: str | None = None
    ) -> None:
        for i, artist in artists:
            artist_aliases_tmp: set[str] = {artist, *self.get_list(artist=artist)}
            artist_aliases: set[str] = {
                artist_alias.replace("artist/", "").replace("tag/", "").replace("character/", "").replace("parody/", "").replace("metadata/", "")
                for artist_alias in artist_aliases_tmp
            }

            url_list = {link for a in artist_aliases for link in await self._add_get_tag_urls(a, choice, True)}
            await q.put((i, artist, url_list))
        await q.put(STOP)

    async def worker_consumer(
        self,
        q: asyncio.Queue[tuple[int, str, list[str]] | object],
        processing_length: int,
        driver: WebDriver,
        fallback_handle: str,
        choice: str | None = None,
        skip_empty: bool = False,
    ) -> None:
        while True:
            item = await q.get()
            if item is STOP:
                return
            item = cast(tuple[int, str, list[str]], item)
            i, artist, url_list = item

            if len(url_list) == 0 and skip_empty:
                print(f"#{i+1} / {processing_length} - {artist} - Nothing found...")
                await self.process_urls(artist, [], choice)
                continue

            await asyncio.to_thread(self._add_open_urls_in_new_tabs, driver, url_list, fallback_handle)
            await asyncio.to_thread(input, f"#{i} / {processing_length} - {artist} - Press ENTER to confirm...")
            confirmed_urls = await asyncio.to_thread(self._add_get_confirmed_urls, driver, fallback_handle)
            await self.process_urls(artist, confirmed_urls, choice)
            await asyncio.to_thread(self._add_close_non_fallback_tabs, driver, fallback_handle)

    async def add_website(self, choice: str, skip_empty: bool) -> None:

        await self._add_activate_dict(self.config, choice=choice)
        driver = cf.init_selenium(False)
        fallback_handle = self._add_ensure_fallback_tab(driver)
        homepages = [self.websiteinfo[key]["object_active"].HOMEPAGE for key in self.websites if key == choice]
        self._add_open_urls_in_new_tabs(
            driver,
            [
                "https://google.com?q=hi",
                "https://ublockorigin.com/",
                "https://www.tampermonkey.net/",
                "https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm",
                *homepages,
            ],
            fallback_handle,
        )
        self._add_userconfirm_console("CONTINUE WHEN EVERYTHING LOADS")
        self._add_close_non_fallback_tabs(driver, fallback_handle)

        self_data_len = len(self.data)
        artists: list[tuple[int, str]] = []
        for i, (artist_name, artist_data) in enumerate(self.data.items()):
            if choice in artist_data:
                print(f"#{i+1} / {self_data_len} - {artist_name} - Already exists...")
                continue
            artists.append((i, artist_name))

        q: asyncio.Queue[tuple[int, str, set[str]] | object] = asyncio.Queue(maxsize=30)
        await asyncio.gather(
            self.worker_consumer(q, self_data_len, driver, fallback_handle, choice, skip_empty), self.worker_producer(artists, q, choice)
        )

    async def add_tags(self) -> None:
        def get_new_tag_name() -> str:
            result = input(f"Please enter the {self.tag_type} which you wanna add: ")
            if result in str(self.data):
                pw = cf.id_generator(6)
                print(
                    f'The given {self.tag_type} "{result}" was found in your subscribed list. '
                    "If this is not the case, please enter the following code:"
                )
                if input(f"Enter {pw} :") != pw:
                    return ""
            while result.startswith(" "):
                result = result[1:]
            while result.endswith(" "):
                result = result[:-1]
            return result

        await self._add_activate_dict(self.config)
        driver = cf.init_selenium(False)
        fallback_handle = self._add_ensure_fallback_tab(driver)
        homepages = [self.websiteinfo[key]["object_active"].HOMEPAGE for key in self.websites]
        self._add_open_urls_in_new_tabs(driver, ["https://google.com?q=hi", "https://ublockorigin.com/", *homepages], fallback_handle)
        self._add_userconfirm_console("CONTINUE WHEN EVERYTHING LOADS")
        self._add_close_non_fallback_tabs(driver, fallback_handle)

        while True:
            print("=" * 20)
            new_tag = get_new_tag_name()
            if not new_tag or new_tag == "":
                continue
            print(f"Gathering for {new_tag}")
            url_list = await self._add_get_tag_urls(new_tag)
            self._add_open_urls_in_new_tabs(driver, url_list, fallback_handle)
            self._add_userconfirm_console(new_tag)
            confirmed_urls = self._add_get_confirmed_urls(driver, fallback_handle)
            await self.process_urls(new_tag, confirmed_urls)
            self._add_close_non_fallback_tabs(driver, fallback_handle)

    def get_list(self, website: str | None = None, artist: str | None = None) -> list[Any]:
        """Returns sorted list of all entries from a given website."""
        taglist = []
        for name, name_data in self.data.items():
            if (artist is None or name == artist) and bool(name_data):
                for website_name, is_there in name_data.items():
                    if (website is None or website_name == website) and bool(is_there):
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

        return sorted([str(x) for x in taglist])

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
                    logging.warning("[%s][%s] - Website key missing.", tag, key)
                else:
                    for key in tag_data:
                        if key not in [
                            *self.websites,
                            "artist-websites",
                            "asmhentai",
                            "doujinscom",
                            "hentaienvy",
                            "hentaiera",
                            "hentaiforce",
                            "hentaifoundry",
                            "hentairead",
                            "nhentainet",
                        ]:
                            logging.warning("[%s][%s] - Key for unsupported website.", tag, key)
        for site in self.websites:
            self.get_list(site)


class CombinedArtistFile(CombinedFile):
    path: Path
    websites: ClassVar[list[str]] = [
        "animepictures",
        "artstation",
        "danbooru",
        "deviantart",
        "gelbooru",
        "hypnohub",
        "kusowanka",
        "newgrounds",
        "patreon",
        "pixiv-artists",
        "reddit",
        "rule34paheal",
        "rule34us",
        "rule34xxx",
        "tumblr",
        "yandere",
    ]
    tag_type = "artist"

    def __init__(self, config: cfg.Config) -> None:
        self.path = config.artists_tags_path()
        super().__init__(config)


class CombinedBooruFile(CombinedFile):
    path: Path
    websites: ClassVar[list[str]] = [
        "animepictures",
        "danbooru",
        "gelbooru",
        "hypnohub",
        "kusowanka",
        "pixiv-tags",
        "rule34paheal",
        "rule34us",
        "rule34xxx",
        "yandere",
    ]
    tag_type = "booru tag"

    def __init__(self, config: cfg.Config) -> None:
        self.path = config.booru_tags_path()
        super().__init__(config)
