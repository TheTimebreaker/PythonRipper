import asyncio
import itertools
import json
import logging
import re
import time
import urllib.parse
from collections.abc import Generator, Iterable
from itertools import chain, combinations, permutations
from pathlib import Path
from typing import Any, ClassVar, NotRequired, TypedDict, cast, override

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from selenium.common.exceptions import NoSuchWindowException, WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.extractor import (
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
    rule34paheal,
    rule34us,
    rule34xxx,
    tumblr,
    yandere,
)
from pythonripper.toolbox.config import ConfigObject, config

STOP = object()

additional_keys = [
    "animepictures",
    "artist-websites",
    "asmhentai",
    "doujinscom",
    "hentaienvy",
    "hentaiera",
    "hentaiforce",
    "hentairead",
    "nhentainet",
    "reddit",
]


class _QtFeedbackWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.app = QApplication.instance() or QApplication([])
        self.loop = asyncio.get_running_loop()
        self.owner_task = asyncio.current_task()
        self.closed_by_user = False
        self.pending: asyncio.Future[str] | None = None

        self.setWindowTitle("Subscription management")
        self.resize(650, 400)
        self.messages = QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Enter response...")
        self.entry.setEnabled(False)
        self.submit_button = QPushButton("Continue")
        self.submit_button.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self.messages)
        layout.addWidget(self.entry)
        layout.addWidget(self.submit_button)

        self.submit_button.clicked.connect(self._submit)
        self.entry.returnPressed.connect(self._submit)

    def info(self, message: str) -> None:
        """Add an info message to the feedback window. Will not block the thread."""
        print(message)
        self.messages.appendPlainText(message)
        if not self.isVisible():
            self.show()

    async def ask(self, message: str) -> str:
        """Ask the user for a response / confirmation in the feedback window. Will block the thread."""
        if self.pending is not None:
            raise RuntimeError("A feedback prompt is already active.")

        print(message)
        self.messages.appendPlainText(message)
        self.entry.clear()
        self.entry.setEnabled(True)
        self.submit_button.setEnabled(True)
        self.pending = self.loop.create_future()
        self.show()
        self.raise_()
        self.entry.setFocus()

        try:
            return await self.pending
        finally:
            self.pending = None
            self.entry.clear()
            self.entry.setEnabled(False)
            self.submit_button.setEnabled(False)

    def _submit(self) -> None:
        if self.pending is not None and not self.pending.done():
            self.pending.set_result(self.entry.text())

    async def process_qt_events(self) -> None:
        while True:
            self.app.processEvents()
            await asyncio.sleep(0.01)

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self.closed_by_user = True
        if self.owner_task is not None and not self.owner_task.done():
            self.owner_task.cancel()
        event.accept()


class WebsiteInfo(TypedDict):
    object: type[scraper.TaggableScraper]
    object_active: NotRequired[scraper.TaggableScraper]


class CombinedFile:
    space_default = "_"
    websiteinfo: ClassVar[dict[str, WebsiteInfo]] = {
        "artstation": {"object": artstation.ArtstationAPI},
        "danbooru": {"object": danbooru.DanbooruAPI},
        "deviantart-artists": {"object": deviantart.DeviantartArtistAPI},
        "deviantart-favorites": {"object": deviantart.DeviantartFavoritesAPI},
        "deviantart-tags": {"object": deviantart.DeviantartTagAPI},
        "gelbooru": {"object": gelbooru.GelbooruAPI},
        "hentaifoundry-artists": {"object": hentaifoundry.HentaiFoundryArtist},
        "hentaifoundry-tags": {"object": hentaifoundry.HentaiFoundryTag},
        "hypnohub": {"object": hypnohub.HypnohubAPI},
        "newgrounds-artists": {"object": newgrounds.NewgroundsArtAPI},
        "newgrounds-favorites": {"object": newgrounds.NewgroundsFavoriteArtAPI},
        "newgrounds-tags": {"object": newgrounds.NewgroundsTagsArtAPI},
        "kusowanka": {"object": kusowanka.KusowankaAPI},
        "patreon": {"object": patreon.PatreonAPI},
        "pixiv-artists": {"object": pixiv.PixivArtistAPI},
        "pixiv-tags": {"object": pixiv.PixivTagAPI},
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

    def __init__(self, config: ConfigObject) -> None:
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
                    temp[key] = sorted(list(dict.fromkeys(value)), key=lambda k: cf.parse_markers(str(k).lower())["parsed"])
                else:
                    temp[key] = value
            return dict(sorted(temp.items(), key=lambda k: cf.parse_markers(str(k[0]).lower())["parsed"]))

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

    async def _add_activate_dict(self, config: ConfigObject, choice: str | None = None) -> None:
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

    async def _add_ensure_fallback_tab(self, driver: WebDriver, fallback_url: str = "about:blank") -> str:
        """
        Make sure there is a dedicated fallback tab and return its window handle.

        This tab stays open permanently so the browser session does not end up with
        zero meaningful tabs during cleanup.
        """
        if not driver.window_handles:
            raise RuntimeError("Driver has no open windows.")

        # Reuse the current tab as fallback if possible.
        fallback_handle = driver.current_window_handle
        await asyncio.to_thread(driver.get, fallback_url)
        return fallback_handle

    async def _add_open_urls_in_new_tabs(self, driver: WebDriver, urls: Iterable[str], fallback_handle: str) -> list[str]:
        """
        Open each URL in its own new tab and return the created tab handles.
        """
        created_handles: list[str] = []

        for url in urls:
            await asyncio.to_thread(driver.switch_to.window, fallback_handle)
            await asyncio.to_thread(driver.switch_to.new_window, "tab")
            new_handle = driver.current_window_handle
            created_handles.append(new_handle)

            try:
                # not good practise to use this, but this should prevent the other threads from firing more requests during the wait
                # hopefully, this is enough to prevent all rate-limits
                time.sleep(1)  # noqa: ASYNC251

                await asyncio.to_thread(driver.get, url)
            except WebDriverException as exc:
                print(f"Failed to open {url!r}: {exc}")
                # If opening fails, close that tab again.
                try:
                    await asyncio.to_thread(driver.close)
                except Exception:
                    pass

                # Switch back to fallback so the driver stays in a sane state.
                await asyncio.to_thread(driver.switch_to.window, fallback_handle)
                created_handles.remove(new_handle)

        return created_handles

    async def _add_close_non_fallback_tabs(self, driver: WebDriver, fallback_handle: str) -> None:
        """
        Close every tab except the fallback tab.
        """
        for handle in list(driver.window_handles):
            if handle == fallback_handle:
                continue

            try:
                await asyncio.to_thread(driver.switch_to.window, handle)
                await asyncio.to_thread(driver.close)
            except NoSuchWindowException:
                continue
            except WebDriverException as exc:
                print(f"Could not close tab {handle!r}: {exc}")

        await asyncio.to_thread(driver.switch_to.window, fallback_handle)

    def _add_userconfirm_console(self, name: str) -> None:
        """
        Simple console-based confirmation.
        The human can manually close bad tabs, then press Enter.
        """
        input(f"\nReview tabs for {name!r}.\n Close the bad tabs manually, keep the good ones open,\n then press Enter to continue...")

    def _add_userconfirm_popup(self, name: str) -> None:
        """
        Optional PySide6 popup confirmation.
        """
        app = QApplication.instance() or QApplication([])
        message_box = QMessageBox()
        message_box.setWindowTitle("Review URLs")
        message_box.setText(f"Review tabs for {name!r}.\n\nClose the bad tabs manually, keep the good ones open,\nthen click OK.")
        message_box.exec()

        if QApplication.instance() is app and not app.parent():
            app.quit()

    async def _add_userconfirm(self, name: str, feedback: _QtFeedbackWindow) -> None:
        await feedback.ask(f"Review tabs for {name!r}.\nClose the bad tabs manually, keep the good ones open, then click Continue.")

    async def _add_get_tag_urls(
        self, tagname: str, website: str | None = None, dont_add_homepage: bool = False, must_have_posts: bool = False
    ) -> list[str]:
        async def task(obj: scraper.TaggableScraper) -> None:
            urls_to_format = []
            if isinstance(obj.URL_TAG, str):
                urls_to_format = [obj.URL_TAG]
            else:
                urls_to_format = [*obj.URL_TAG]
            logging.info(urls_to_format)

            found_some = False
            tagnames: set[str] = set()
            if obj.IS_CASE_SENSITIVE is True:
                tagnames.update(cf.case_permutations(tagname))
            else:
                tagnames.add(tagname.lower())

            # kusowanka special case
            if isinstance(obj, kusowanka.KusowankaAPI):
                kuso_tagnames: set[str] = set()
                for this_tagname in tagnames:
                    if not any(this_tagname.startswith(f"{x}/") for x in ("artist", "character", "metadata", "parody", "tag")):
                        kuso_tagnames.update(
                            (
                                f"artist/{this_tagname}",
                                f"character/{this_tagname}",
                                f"metadata/{this_tagname}",
                                f"parody/{this_tagname}",
                                f"tag/{this_tagname}",
                            )
                        )
                    else:
                        kuso_tagnames.add(this_tagname)
                tagnames = kuso_tagnames
            logging.info("tagnames: %s", tagnames)

            for url_to_format, local_tagname in itertools.product(urls_to_format, tagnames):
                formatted_tagname = obj.format_tagname(local_tagname)
                if not formatted_tagname:
                    continue
                this_url = url_to_format.format(tagname=formatted_tagname)
                this_tagname = local_tagname

                try:
                    exists = await obj.does_this_exist(this_tagname)
                    if exists:
                        if not must_have_posts or await obj.does_this_have_posts(this_tagname):
                            result.add(this_url)
                            found_some = True
                    else:
                        continue
                except json.decoder.JSONDecodeError, ConnectionAbortedError, ConnectionRefusedError, cf.ExtractorExitError, cf.ExtractorStopError:
                    pass

            if found_some is False:
                if dont_add_homepage is False:
                    result.add(obj.HOMEPAGE)

        tagname = cf.parse_markers(tagname)["parsed"]

        result: set[str] = set()
        tasks: list[asyncio.Task[None]] = []
        for key in self.websites:
            if website is None or website == key:
                obj = self.websiteinfo[key]["object_active"]
                tasks.append(asyncio.create_task(task(obj)))
        await asyncio.gather(*tasks)
        return list(result)

    async def _add_get_confirmed_urls(self, driver: WebDriver, fallback_handle: str) -> list[str]:
        """
        Return the URLs of all currently open tabs except the fallback tab.
        """
        confirmed_urls: list[str] = []

        # Snapshot because window_handles may change if the browser is touched.
        for handle in list(driver.window_handles):
            if handle == fallback_handle:
                continue

            try:
                await asyncio.to_thread(driver.switch_to.window, handle)
                url = driver.current_url
                confirmed_urls.append(url)
            except NoSuchWindowException:
                # User may have closed it between reading handles and switching.
                continue
            except WebDriverException as exc:
                print(f"Could not read URL from tab {handle!r}: {exc}")

        # Restore focus to fallback at the end.
        await asyncio.to_thread(driver.switch_to.window, fallback_handle)
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
                        tag = obj.invert_formatting(tag_formatted)
                        while tag.startswith((" ", "+")):
                            tag = tag[1:]
                        while tag.endswith((" ", "+")):
                            tag = tag[:-1]

                        if re.match(r"^(?:\s?[A-Za-z]\s)+$", tag):
                            raise ValueError("Tag %s was detected with spaces from url %s and pattern %s", tag, url, obj.TAG_PATTERN)
                        try:
                            new_tag_obj[key].append(tag)
                        except AttributeError:
                            existing_value = new_tag_obj[key]
                            if not existing_value:
                                new_tag_obj[key] = [tag]
                            elif isinstance(existing_value, (int, str)):
                                new_tag_obj[key] = [existing_value, tag]
                            else:
                                raise TypeError(
                                    "theres some unsupported value type in your data! %s %s", existing_value, type(existing_value)
                                ) from AttributeError
                        break
                    except AttributeError:
                        continue
            else:
                print(f"Could not verify link {url}")
        self.data[new_tag] = new_tag_obj
        await self.write()

    async def worker_producer(
        self, artists: list[tuple[int, str]], q: asyncio.Queue[tuple[int, str, set[str]] | object], choice: str, must_have_posts: bool
    ) -> None:
        def is_formatted_existing_alias_in_formatted_artist_aliases(formatted_existing_alias: str) -> Generator[str]:
            for artist_alias in artist_aliases:
                formatted_artist_alias = obj.format_tagname(artist_alias)
                if formatted_artist_alias and formatted_existing_alias == formatted_artist_alias:
                    yield artist_alias

        obj = self.websiteinfo[choice]["object_active"]
        for i, artist in artists:
            is_case_sensitive = obj.IS_CASE_SENSITIVE
            artist_aliases_tmp: set[str] = {artist, *self.get_list(artist=artist, remove_bypass_markers=True)}
            artist_aliases: set[str] = {
                artist_alias.replace("artist/", "")
                .replace("tag/", "")
                .replace("character/", "")
                .replace("parody/", "")
                .replace("metadata/", "")
                .replace("u/", "")
                .replace("r/", "")
                for artist_alias in artist_aliases_tmp
            }
            # Case sensitive check
            if not is_case_sensitive:
                artist_aliases = {x.lower() for x in artist_aliases}

            # kusowanka special case because they use the category in the url
            if isinstance(obj, kusowanka.KusowankaAPI):
                kusowanka_aliases: set[str] = set()
                for tn in artist_aliases:
                    kusowanka_aliases.update(
                        (
                            f"artist/{tn}",
                            f"character/{tn}",
                            f"metadata/{tn}",
                            f"parody/{tn}",
                            f"tag/{tn}",
                        )
                    )
                artist_aliases = kusowanka_aliases

            # Removes any alias that already exists for the website and artist
            list_of_bypass_markers: list[str] = []
            bypass_configs = [
                self.config.settings.general.allow_blacklist_bypass,
                self.config.settings.general.allow_contentfilter_bypass,
            ]
            for me in bypass_configs:
                if me:
                    list_of_bypass_markers.append(me)
            bypass_permutations = list(
                chain.from_iterable(
                    permutations(combo) for r in range(len(list_of_bypass_markers) + 1) for combo in combinations(list_of_bypass_markers, r)
                )
            )
            logging.info("artist_aliases before discarding=%s", artist_aliases)
            discared_aliases: set[str] = set()
            for existing_alias in self.get_list(website=choice, artist=artist, remove_bypass_markers=True):
                # removes the literal existing alias
                discared_aliases.add(existing_alias)

                # formats existing alias and if that matches the preprocessed list, original gets removed
                formatted_existing_alias = obj.format_tagname(existing_alias)
                if formatted_existing_alias:
                    discared_aliases.add(formatted_existing_alias)
                    for placeholder_ in is_formatted_existing_alias_in_formatted_artist_aliases(formatted_existing_alias):
                        discared_aliases.add(placeholder_)

                # removes potential flag bypasses from the string
                for combination in bypass_permutations:
                    target_tmp = existing_alias
                    if combination:
                        for element in combination:
                            target_tmp = f"{element}{target_tmp}{element}"
                    discared_aliases.add(target_tmp)

            logging.info("discared_aliases=%s", discared_aliases)
            for discard in discared_aliases:
                artist_aliases.discard(discard)

            logging.info("artist_aliases after discarding=%s", artist_aliases)

            url_list = {link for a in artist_aliases for link in await self._add_get_tag_urls(a, choice, True, must_have_posts)}
            await q.put((i, artist, url_list))
        await q.put(STOP)

    async def worker_consumer(
        self,
        q: asyncio.Queue[tuple[int, str, list[str]] | object],
        processing_length: int,
        driver: WebDriver,
        fallback_handle: str,
        feedback: _QtFeedbackWindow,
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
                feedback.info(f"#{i+1} / {processing_length} - {artist} - Nothing found...")
                await self.process_urls(artist, [], choice)
                continue

            logging.info("url_list: %s", url_list)
            await self._add_open_urls_in_new_tabs(driver, url_list, fallback_handle)
            await feedback.ask(f"#{i+1} / {processing_length} - {artist} - Click Continue to confirm.")
            confirmed_urls = await self._add_get_confirmed_urls(driver, fallback_handle)
            await self.process_urls(artist, confirmed_urls, choice)
            await self._add_close_non_fallback_tabs(driver, fallback_handle)

    async def add_website(
        self, website_choice: str, skip_empty: bool = True, check_existing_again: bool = False, must_have_posts: bool = False, starting_index: int = 0
    ) -> None:
        feedback = _QtFeedbackWindow()
        qt_task = asyncio.create_task(feedback.process_qt_events())

        try:
            await self._add_website_with_feedback(website_choice, skip_empty, check_existing_again, must_have_posts, starting_index, feedback)
        except asyncio.CancelledError:
            if not feedback.closed_by_user:
                raise
        finally:
            qt_task.cancel()

    async def _add_website_with_feedback(
        self,
        website_choice: str,
        skip_empty: bool,
        check_existing_again: bool,
        must_have_posts: bool,
        starting_index: int,
        feedback: _QtFeedbackWindow,
    ) -> None:
        feedback.info(r""" /\_/\
( o.o )
 > ^ <
Hello! Please wait until the web browser has finished initializing.""")
        await asyncio.sleep(0)

        await self._add_activate_dict(self.config, choice=website_choice)
        driver = cf.init_selenium(False)
        fallback_handle = await self._add_ensure_fallback_tab(driver)
        homepages = [self.websiteinfo[key]["object_active"].HOMEPAGE for key in self.websites if key == website_choice]
        await self._add_open_urls_in_new_tabs(
            driver,
            [
                "https://chromewebstore.google.com/detail/ublock-origin-lite/ddkjiahejlhfcafbddmgiahcphecmpfh",
                *homepages,
            ],
            fallback_handle,
        )
        await feedback.ask("Review the tabs that have opened. If they opened successfully, click Continue.")
        await self._add_close_non_fallback_tabs(driver, fallback_handle)

        self_data_len = len(self.data)
        artists: list[tuple[int, str]] = []
        for i, (artist_name, artist_data) in enumerate(self.data.items()):
            if i < starting_index:
                continue
            if website_choice in artist_data and not check_existing_again:
                feedback.info(f"#{i+1} / {self_data_len} - {artist_name} - Already exists...")
                continue
            artists.append((i, artist_name))

        q: asyncio.Queue[tuple[int, str, set[str]] | object] = asyncio.Queue(maxsize=200)
        await asyncio.gather(
            self.worker_consumer(q, self_data_len, driver, fallback_handle, feedback, website_choice, skip_empty),
            self.worker_producer(artists, q, website_choice, must_have_posts),
        )

    async def add_tags(self) -> None:
        feedback = _QtFeedbackWindow()
        qt_task = asyncio.create_task(feedback.process_qt_events())

        try:
            await self._add_tags_with_feedback(feedback)
        except asyncio.CancelledError:
            if not feedback.closed_by_user:
                raise
        finally:
            qt_task.cancel()

    async def _add_tags_with_feedback(self, feedback: _QtFeedbackWindow) -> None:
        feedback.info(r""" /\_/\
( o.o )
 > ^ <
Hello! Please wait until the web browser has finished initializing.""")
        await asyncio.sleep(0)

        async def get_new_tag_name() -> str:
            result = await feedback.ask(f"Please enter the {self.tag_type} which you want to add:")
            if result in str(self.data):
                password = cf.id_generator(6)
                feedback.info(
                    f'The given {self.tag_type} "{result}" was found in your '
                    "subscribed list. If this is not the case, enter the "
                    "confirmation code shown in the next prompt."
                )
                if await feedback.ask(f"Enter {password}:") != password:
                    return ""

            return result.strip()

        await self._add_activate_dict(self.config)
        driver = cf.init_selenium(False)
        fallback_handle = await self._add_ensure_fallback_tab(driver)
        homepages = [self.websiteinfo[key]["object_active"].HOMEPAGE for key in self.websites]
        await self._add_open_urls_in_new_tabs(
            driver,
            [
                "https://chromewebstore.google.com/detail/ublock-origin-lite/ddkjiahejlhfcafbddmgiahcphecmpfh/",
                *homepages,
            ],
            fallback_handle,
        )
        await feedback.ask("Review the tabs that have opened. If they opened successfully, click Continue.")
        await self._add_close_non_fallback_tabs(driver, fallback_handle)

        while True:
            feedback.info("=" * 20)
            new_tag = await get_new_tag_name()
            if not new_tag:
                continue

            feedback.info(f"Gathering links for '{new_tag}'")
            url_list = await self._add_get_tag_urls(new_tag)
            await self._add_open_urls_in_new_tabs(driver, url_list, fallback_handle)
            await self._add_userconfirm(new_tag, feedback)
            confirmed_urls = await self._add_get_confirmed_urls(driver, fallback_handle)
            await self.process_urls(new_tag, confirmed_urls)
            await self._add_close_non_fallback_tabs(driver, fallback_handle)

    def get_list(self, *, website: str | None = None, artist: str | None = None, remove_bypass_markers: bool = False) -> set[str]:
        """Returns sorted list of all entries from a given website or tag/artist."""
        taglist: set[str | int] = set()

        # TOP LEVEL TAGNAMES
        # these are the main names where the website specific tagnames are stored within
        for name, name_data in self.data.items():
            bypass_parsed = cf.parse_markers(name)

            input_name_selector = artist is None or name == artist or bypass_parsed["parsed"] == artist
            data_is_there = bool(name_data)
            if not (input_name_selector and data_is_there):
                continue
            for website_name, is_there in name_data.items():
                website_parsed = cf.parse_markers(website_name)

                input_website_selector = website is None or website_name == website or website_parsed["parsed"] == website
                websitedata_is_there = bool(is_there)
                if not (input_website_selector and websitedata_is_there):
                    continue

                if isinstance(is_there, (str, int)):
                    is_there = cf.apply_markers([bypass_parsed, website_parsed], str(is_there))
                    taglist.add(is_there)
                elif isinstance(is_there, list):
                    for sublink in is_there:
                        sublink = cf.apply_markers([bypass_parsed, website_parsed], str(sublink))
                        taglist.add(sublink)

        if remove_bypass_markers:
            return {cf.parse_markers(str(x))["parsed"] for x in taglist}
        return {str(x) for x in taglist}

    def check_keys(self) -> None:
        tags_by_website: dict[str, list[str]] = {website: [] for website in (*self.websites, *additional_keys)}
        for tag, tag_data in self.data.items():
            for website_key in self.websites:

                # Website key checks: missing keys and unsupported keys
                if website_key not in tag_data.keys():
                    logging.warning("[%s][%s] - Website key missing.", tag, website_key)
                else:
                    for website_key in tag_data:
                        if website_key not in [*self.websites, *additional_keys]:
                            logging.warning("[%s][%s] - Key for unsupported website.", tag, website_key)

            assert isinstance(tag_data, dict)
            for _website, _websitedata in tag_data.items():
                _website = cf.parse_markers(_website)["parsed"]
                assert isinstance(_website, str)
                assert isinstance(_websitedata, (list, bool, str, int))

                if isinstance(_websitedata, bool):
                    if _websitedata:
                        raise ValueError
                    continue

                if not isinstance(_websitedata, list):
                    _websitedata = [_websitedata]

                for _element in _websitedata:
                    _element = cf.parse_markers(_element)["parsed"]
                    if _element in tags_by_website[_website]:
                        logging.warning(
                            "[%s] The tag \x1b[3m%s\x1b[0m from sorting tag \x1b[3m%s\x1b[0m appears multiple times in your json file!",
                            _website,
                            _element,
                            tag,
                        )
                    tags_by_website[_website].append(_element)


class _CombinedArtistFile(CombinedFile):
    path: Path
    websites: ClassVar[list[str]] = [
        "artstation",
        "danbooru",
        "deviantart-artists",
        "gelbooru",
        "hypnohub",
        "hentaifoundry-artists",
        "kusowanka",
        "newgrounds-artists",
        "patreon",
        "pixiv-artists",
        "rule34paheal",
        "rule34us",
        "rule34xxx",
        "tumblr",
        "yandere",
    ]
    tag_type = "artist"

    def __init__(self, config: ConfigObject) -> None:
        self.path = config.paths.artists_tags_path()
        super().__init__(config)


class _CombinedBooruFile(CombinedFile):
    path: Path
    websites: ClassVar[list[str]] = [
        "danbooru",
        "deviantart-tags",
        "gelbooru",
        "hentaifoundry-tags",
        "hypnohub",
        "kusowanka",
        "newgrounds-tags",
        "pixiv-tags",
        "rule34paheal",
        "rule34us",
        "rule34xxx",
        "yandere",
    ]
    tag_type = "booru tag"

    def __init__(self, config: ConfigObject) -> None:
        self.path = config.paths.booru_tags_path()
        super().__init__(config)


class _CombinedFavoritesFile(CombinedFile):
    path: Path
    websites: ClassVar[list[str]] = [
        "deviantart-favorites",
        "newgrounds-favorites",
    ]
    tag_type = "favorites"

    def __init__(self, config: ConfigObject) -> None:
        self.path = config.paths.favorites_path()
        super().__init__(config)


combined_artist_file = _CombinedArtistFile(config)
combined_tags_file = _CombinedBooruFile(config)
combined_favorites_file = _CombinedFavoritesFile(config)
