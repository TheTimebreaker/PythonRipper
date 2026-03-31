"""Main module for interacting with https://anime-pictures.net/ ."""

import itertools
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any, final

import aiofiles
import asynciolimiter
import bs4
import curl_cffi

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


@final
class Animepictures(scraper.BooruScraper):
    API_URL = "https://anime-pictures.net/posts"
    POST_PATTERN = r"(?:https?://)?(?:www\.)?anime-pictures\.net/posts/(\d+)"

    ME = "animepictures"
    LIMIT = asynciolimiter.Limiter(0.5, max_burst=10)
    SPACE_REPLACE = "+"

    async def init(self) -> bool:
        self.credentials_path = self.config._credentials_path() / "animepictures_credentials.json"
        self.page_start = 0
        self.download_headers = {"Cookie": "sitelang=en; kira=6"}
        self.session = curl_cffi.requests.AsyncSession(timeout=cf.asynctimeoutseconds(), impersonate="chrome101")

        async def _login() -> bool:
            try:
                async with aiofiles.open(self.credentials_path) as file:
                    data = json.loads(await file.read())
                username, password = data["username"], data["password"]
            except KeyError, FileNotFoundError:
                logging.error(
                    "[ANIMEPICTURES] - No valid credentials found. Please create a credentials json file at %s "
                    "containing 'username' and 'password' of your account. "
                    "Do NOT use an actual account for this; use a burner, since the password will be stored"
                    "in CLEAR TEXT on an unprotected text file on your disk.",
                    self.credentials_path,
                )
                return False

            json_request = {"login": username, "password": password, "time_zone": "Europe/Berlin"}
            await self.LIMIT.wait()
            res = await self.session.post("https://api.anime-pictures.net/api/v3/auth", json=json_request)
            if res.status_code != 200:
                logging.error("[ANIMEPICTURES] - Login failed, status code %s", res.status_code)
                raise ConnectionRefusedError
            logging.info("[ANIMEPICTURES] - Login succeeded")
            return True

        async def _set_explicit_images() -> bool:
            try:
                allow = self.config.data["extractor"]["animepictures"]["allow_erotic_images"]
                if not (allow is True or allow is False):
                    raise KeyError
            except KeyError:
                logging.error(
                    "[ANIMEPICTURES] - No setting found regarding allowance of erotic imagery. Please set it in settings at"
                    '["extractor"]/["animepictures"]/["allow_erotic_images"] by setting it to either true or false. '
                )
                return False

            await self.LIMIT.wait()
            res = await self.session.get("https://api.anime-pictures.net/api/v3/profile?lang=en")
            if res.status_code != 200:
                logging.error("[ANIMEPICTURES] - Profile settings checkup failed, status code %s", res.status_code)
                raise ConnectionRefusedError
            if not res.json()["user"]["jvwall_block_erotic"]:  # type: ignore
                logging.info("[ANIMEPICTURES] - Explicit images are enabled in user settings.")
                return True
            logging.warning("[ANIMEPICTURES] - Explicit images are not enabled in user settings. Attempting to fix...")
            json = {"jvwall_block_erotic": False}
            await self.LIMIT.wait()
            res = await self.session.put("https://api.anime-pictures.net/api/v3/profile?lang=en", json=json)
            if res.status_code != 200:
                logging.error("[ANIMEPICTURES] - Profile settings checkup failed, status code %s", res.status_code)
                raise ConnectionRefusedError
            logging.info("[ANIMEPICTURES] - Changing user settings to allow explicit images was successfull.")
            return True

        if not await _login():
            return False
        if not await _set_explicit_images():
            return False
        return True

    async def does_this_exist(self, tagname: str) -> bool:
        await self.LIMIT.wait()
        res = await self.session.get(self.API_URL, params={"page": 0, "search_tag": self.format_tagname(tagname), "lang": "en"})
        return "in request 0 pictures" not in res.text

    async def _get_post_data(self, post_id: str | None = None, _json_data: dict[Any, Any] | None = None) -> scraper.PostData:
        async def _get_post_html(post_id: str) -> str:
            url = f"{self.API_URL}/{post_id}"
            await self.LIMIT.wait()
            res = await self.session.get(url)
            if res.status_code != 200:
                logging.error("[ANIMEPICTURES] - Request to %s return status code %s", url, res.status_code)
                raise ConnectionRefusedError
            logging.info("[ANIMEPICTURES] - Request to %s return status code %s", url, res.status_code)
            return str(res.text)

        def _filter_tags_by_type(
            alltags: list[bs4.BeautifulSoup] | bs4.element.ResultSet,  # type: ignore
            keys: str | list[str],
        ) -> list[bs4.BeautifulSoup]:
            """Filters a bs4 elements list of all tag <li>s by the <a>.child class key,
            which determines the kind of tag (e.g. artist, character, etc)"""
            if isinstance(keys, str):
                keys = [keys]
            return [item for item in alltags if any(item.find("a", {"class": key}) for key in keys)]

        def _extract_tags_from_html(
            tags_html: list[bs4.BeautifulSoup] | bs4.element.ResultSet,  # type: ignore
        ) -> list[str]:
            """Extracts tagnames as str from a list of tag <li>s"""
            return [tag_html.find("a").contents[0] for tag_html in tags_html]  # type: ignore

        if post_id is None:
            raise ValueError("No post id given. Other fetching methods are impossible.")

        soup = bs4.BeautifulSoup(await _get_post_html(post_id), "lxml")
        all_tags_outer_html = soup.find("ul", {"class": "tags"})
        all_tags_html = all_tags_outer_html.find_all("li")  # type: ignore

        tagdata = scraper.TagsData(
            artists=_extract_tags_from_html(_filter_tags_by_type(all_tags_html, "artist")),
            characters=_extract_tags_from_html(_filter_tags_by_type(all_tags_html, "character")),
            metatags=[],
            parodies=_extract_tags_from_html(_filter_tags_by_type(all_tags_html, "copyright")),
            tags=_extract_tags_from_html(_filter_tags_by_type(all_tags_html, ["reference", "object"])),
        )

        download_url_tmp = soup.find("a", {"class": "icon-download"})
        assert download_url_tmp
        download_url = str(download_url_tmp["href"])
        extension = f.match_extension(download_url)
        assert extension

        return scraper.PostData(
            identifier=post_id,
            elements=scraper.PostElementLinks(download_url=download_url, extension=extension),
            tags=tagdata,
        )

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        async def get_tag_html(tag_name: str, page: int) -> str:
            params: dict[str, str | int] = {"page": page, "search_tag": tag_name, "lang": "en"}
            logging.info("[ANIMEPICTURES] - %s  %s", self.API_URL, params)
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)
            if res.status_code != 200:
                logging.error("[ANIMEPICTURES] - Request to tag %s return status code %s", tag_name, res.status_code)
                raise ConnectionRefusedError
            logging.info("[ANIMEPICTURES] - Request to tag %s return status code %s", tag_name, res.status_code)
            return str(res.text)

        def _extract_postids_from_html(html: str) -> list[str]:
            """Extracts post IDs as ints from html of tag page"""
            soup = bs4.BeautifulSoup(html, "lxml")
            all_imgs_outer_html = soup.find("div", {"class": "central-block"})
            all_imgs_html = all_imgs_outer_html.find_all("div", {"class": "img-block"})  # type: ignore

            postids: list[str] = []
            for img_html in all_imgs_html:
                tmp = img_html.find("a")
                if tmp is None:
                    raise ValueError("HTML element evaluated to None")
                href = str(tmp["href"])
                postid = re.search(r"/posts/(\d+)", href)
                assert postid
                postids.append(str(postid.group(1)))
            return postids

        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        for page in itertools.count(start=self.page_start):
            post_ids = _extract_postids_from_html(await get_tag_html(tagname, page))
            if len(post_ids) == 0:
                logging.info("[ANIMEPICTURES] - End of tag %s reached; no more files reported.", tagname)
                return

            for post_id in post_ids:
                if str(post_id) in update_ids:
                    logging.info("[ANIMEPICTURES] - Update ID encountered in tag %s .", tagname)
                    return
                yield await self._get_post_data(post_id)
