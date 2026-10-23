"""Main module for interacting with https://anime-pictures.net/ ."""

import asyncio
import itertools
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Literal, final, override

import aiofiles
import asynciolimiter
import curl_cffi

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


@final
class Animepictures(scraper.DownloadhistoryScraper):
    HOMEPAGE = "https://anime-pictures.net"
    API_URL = "https://api.anime-pictures.net/api"
    URL_TAG = "https://anime-pictures.net/posts?search_tag={tagname}&lang=en"
    POST_PATTERN = r"(?:https?://)?(?:www\.)?anime-pictures\.net/posts/(\d+)"
    TAG_PATTERN = r"https://(?:www\.)?anime\-pictures\.net/posts\?(?:.+)?search_tag=([^/&\?]+)"

    ME = "animepictures"
    WEBSITE_NAME = ME
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "+"
    page_start = 0

    session: curl_cffi.AsyncSession

    async def init(self) -> bool:
        self.credentials_path = self.config.paths._credentials() / "animepictures_credentials.json"
        self.page_start = 0
        self.session = curl_cffi.requests.AsyncSession(timeout=cf.asynctimeoutseconds(), impersonate="chrome142")
        self.cookies = self.download_cookies = [{"name": "kira", "value": "2", "domain": ".anime-pictures.net"}]
        for cookie in self.cookies:
            self.session.cookies.set(**cookie)

        async def _login() -> bool:
            try:
                async with aiofiles.open(self.credentials_path) as file:
                    data = json.loads(await file.read())
                username, password = data["username"], data["password"]
            except KeyError, FileNotFoundError:
                logging.error(
                    "[%s] - No valid credentials found. Please create a credentials json file at %s "
                    "containing 'username' and 'password' of your account. "
                    "Do NOT use an actual account for this; use a burner, since the password will be stored"
                    "in CLEAR TEXT on an unprotected text file on your disk.",
                    self.ME.upper(),
                    self.credentials_path,
                )
                return False

            json_request = {"login": username, "password": password, "time_zone": "Europe/Berlin"}
            await self.LIMIT.wait()
            res = await self.session.post("https://api.anime-pictures.net/api/v3/auth", json=json_request)
            if res.status_code != 200:
                logging.error("[%s] - Login failed, status code %s", self.ME.upper(), res.status_code)
                raise ConnectionRefusedError
            logging.info("[%s] - Login succeeded", self.ME.upper())
            return True

        async def _set_explicit_images() -> bool:
            allow = self.config.settings.extractor.animepictures.allow_erotic_images

            await self.LIMIT.wait()
            res = await self.session.get("https://api.anime-pictures.net/api/v3/profile?lang=en")
            if res.status_code != 200:
                logging.error("[%s] - Profile settings checkup failed, status code %s", self.ME.upper(), res.status_code)
                raise ConnectionRefusedError
            if res.json()["user"]["jvwall_block_erotic"] == (not allow):  # type: ignore
                logging.info("[%s] - Explicit images are set as wanted.", self.ME.upper())
                return True

            logging.warning("[%s] - Explicit images are not set as wanted. Attempting to fix...", self.ME.upper())
            json = {"jvwall_block_erotic": (not allow)}
            await self.LIMIT.wait()
            res = await self.session.put("https://api.anime-pictures.net/api/v3/profile?lang=en", json=json)
            if res.status_code != 200:
                logging.error("[%s] - Profile settings checkup failed, status code %s", self.ME.upper(), res.status_code)
                raise ConnectionRefusedError
            logging.info("[%s] - Changing user settings to set explicit images as wanted was successful.", self.ME.upper())
            return True

        if not await _login():
            return False
        if not await _set_explicit_images():
            return False
        return True

    @override
    async def does_this_exist(self, tagname: str) -> bool:
        tagname = self.format_tagname(tagname)
        api_url = self.API_URL + "/v3/posts"
        params: dict[str, str | int] = {
            "search_tag": tagname,
            "lang": "en",
        }

        params["page"] = str(self.page_start)
        res = await self.request(api_url, params=params)
        resjson: dict[str, Any] = res.json()  # type: ignore
        return bool(resjson.get("posts_count", 0) > 0)

    @override
    async def does_this_have_posts(self, tagname: str) -> bool:
        # does_this_exist() already checks existance by checking post count.
        # if it exists, it will have posts, because thats what defines "existing" it here
        return True

    async def request(self, url: str, params: dict[str, str | int] | None = None) -> curl_cffi.Response:
        for i in (30, 30, 30, 30, 60, 60, 60, 60):
            await self.LIMIT.wait()
            res = await self.session.get(url, params=params)
            if res.status_code == 429:
                logging.warning("[%s] - Rate limited, waiting %s seconds", self.ME.upper(), i)
                await asyncio.sleep(i)
                continue
            return res
        raise cf.ExtractorStopError("Probably hit a hard rate limit")

    def format_tagname(self, tagname: str) -> str:
        return tagname.replace(" ", self.SPACE_REPLACE)

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[Any, Any] | None = None) -> scraper.PostData:
        def _get_filehash(data: dict[Any, Any]) -> str:
            try:
                md5 = data.get("md5", None)
                if not isinstance(md5, str):
                    raise cf.InterruptError
                return md5

            except cf.InterruptError as error:
                msg = f"Could not get the md5 hash of post {post_id}"
                logging.error("[%s] - %s", self.ME.upper(), msg)
                raise cf.ExtractorSkipError(msg) from error

        def get_elements(data: dict[Any, Any], filehash: str) -> scraper.PostElementLinks:
            try:
                data_extension = data.get("ext", None)
                if not isinstance(data_extension, str):
                    raise cf.InterruptError

                download_url = f"https://oimages.anime-pictures.net/{filehash[:3]}/{filehash}{data_extension}"
                ext = f.match_extension(download_url)
                if not ext:
                    raise cf.InterruptError
                return scraper.PostElementLinks(download_url=download_url, extension=ext)

            except cf.InterruptError as error:
                msg = f"Could not extract download URL from post {post_id}"
                logging.error("[%s] - %s", self.ME.upper(), msg)
                raise cf.ExtractorSkipError(msg) from error

        def _get_tags(data: dict[Any, Any]) -> scraper.TagsData:
            try:
                tags_data: list[dict[str, dict[str, str | int | None | Literal[False]]]] | None = data.get("tags", None)
                if not isinstance(tags_data, list):
                    raise cf.InterruptError
                _artists: list[str] = []
                _characters: list[str] = []
                _meta: list[str] = []
                _parodies: list[str] = []
                _tags: list[str] = []

                for tag in tags_data:
                    tag_name: str | None = tag.get("tag", {}).get("tag", None)  # type: ignore
                    tag_type: int | None = tag.get("tag", {}).get("type", None)  # type: ignore
                    if tag_name is None or tag_type is None:
                        raise cf.InterruptError
                    match tag_type:
                        case 1:
                            _characters.append(tag_name)
                        case 2 | 5 | 7:
                            _tags.append(tag_name)
                        case 3 | 6:
                            _parodies.append(tag_name)
                        case 4:
                            _artists.append(tag_name)
                        case _:
                            logging.error(
                                "[%s] - Could not determine tag type %s of tag %s for post %s", self.ME.upper(), tag_type, tag_name, post_id
                            )

                return scraper.TagsData(
                    artists=_artists,
                    characters=_characters,
                    metatags=_meta,
                    parodies=_parodies,
                    tags=_tags,
                )
            except cf.InterruptError as error:
                if self.config.settings.extractor.animepictures.always_fetch_tags is True:
                    msg = f"Could not extract tags from post {post_id}"
                    logging.error("[%s] - %s", self.ME.upper(), msg)
                    raise cf.ExtractorSkipError(msg) from error
                return scraper.TagsData(tags=[])

        if json_data is None:
            if post_id is None:
                raise ValueError("Neither postid nor jsondata were given (one is required).")
            res = await self.request(f"{self.API_URL}/v3/posts/{post_id}")
            json_data = res.json().get("post")  # type: ignore
            tag_data = res.json().get("tags")  # type: ignore
            json_data["tags"] = tag_data
        else:
            post_id = str(json_data.get("id"))
            if self.config.settings.extractor.animepictures.always_fetch_tags is True and not json_data.get("tags", False):
                return await self._get_post_data(post_id)

        filehash = _get_filehash(json_data)
        elements = get_elements(json_data, filehash)
        tags = _get_tags(json_data)

        is_mature = json_data.get("erotics", 1) == 2

        return scraper.PostData(
            identifier=post_id,
            filehash=filehash,
            elements=elements,
            tags=tags,
            rating="mature" if is_mature else "general",
        )

    async def _fetch_posts(
        self, tagname: str, update_ids: list[str] | None = None, ignore_contentfilters: bool = False  # noqa: ARG002
    ) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        api_url = self.API_URL + "/v3/posts"
        params: dict[str, str | int] = {
            "search_tag": tagname,
            "lang": "en",
        }

        for page in itertools.count(start=self.page_start):
            params["page"] = str(page)
            res = await self.request(api_url, params=params)
            resjson: dict[str, Any] = res.json()  # type: ignore
            posts: list[dict[str, Any]] = resjson.get("posts")  # type: ignore

            if not posts:
                return

            for post in posts:
                post_id = str(post.get("id"))
                if str(post_id) in update_ids:
                    logging.info("[%s] - Update ID encountered in tag %s .", self.ME.upper(), tagname)
                    return
                yield await self._get_post_data(post_id=post_id, json_data=post)
