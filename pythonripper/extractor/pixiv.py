"""Main module for interacting with https://www.pixiv.net/ ."""

import hashlib
import json
import logging
import re
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, final

import aiofiles
import asynciolimiter
import httpx

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


class PixivRoot(scraper.DownloadhistoryScraper):
    HOMEPAGE = "https://www.pixiv.net"

    client_id = "MOBrBDS8blbauoSck0ZfDbtuzpyT"  # hard coded, from the app afaik
    client_secret = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"  # same
    hash_secret = "28c1fdd170a5204386cb1313c7077b34f83e4aaf4aa829ce78c231e05b0bae2c"
    base_api_url = "https://app-api.pixiv.net"
    BASE_PATTERN = r"(?:https?://)?(?:www\.|touch\.)?pixiv\.net"

    ILLUST_PATTERN = (
        r"(?:https?://)?(?:(?:www\.|touch\.)?pixiv\.net"  # stolen from gallery-dl.extractor.pixiv
        r"/(?:(?:en/)?artworks/"
        r"|member_illust\.php\?(?:[^&]+&)*illust_id=)(\d+)"
        r"|(?:i(?:\d+\.pixiv|\.pximg)\.net"
        r"/(?:(?:.*/)?img-[^/]+/img/\d{4}(?:/\d\d){5}|img\d+/img/[^/]+)"
        r"|img\d*\.pixiv\.net/img/[^/]+|(?:www\.)?pixiv\.net/i)/(\d+))"
    )
    POST_PATTERN = r"(?:https?://)?(?:www\.)?pixiv\.net(?:/en|/jp)/artworks/(\d+)"
    USER_PATTERN = BASE_PATTERN + r"/(?:(?:en/)?u(?:sers)?/|member\.php\?id=|(?:mypage\.php)?#id=)(\d+)(?:$|[?#])?"

    LIMIT = asynciolimiter.LeakyBucketLimiter(3, capacity=200)
    SPACE_REPLACE = "_"
    IS_GOOGLE_SEARCHABLE = False

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.download_headers = {"Referer": "https://app-api.pixiv.net/"}
        self.refresh_token: str
        self.access_token: str
        self.username: str
        self.valid_until: float
        self.credentials_path = self.config._credentials_path() / "pixiv_credentials.json"
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)

        def default_header() -> Literal[True]:
            self.timenow = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
            self.timehash = hashlib.md5((self.timenow + self.hash_secret).encode()).hexdigest()
            self.headers = {
                "User-Agent": "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)",
                "Accept-Language": "en_US",
                "App-OS": "android",
                "App-OS-Version": "4.4.2",
                "App-Version": "5.0.145",
                "X-Client-Time": self.timenow,
                "X-Client-Hash": self.timehash,
            }
            return True

        def bearer_header() -> Literal[True]:
            if not self.headers:
                default_header()
            self.headers["Authorization"] = f"Bearer {self.access_token}"
            return True

        async def get_token() -> bool:
            try:
                async with aiofiles.open(self.credentials_path) as file:
                    data = json.loads(await file.read())
                    self.refresh_token = data["refresh_token"]
            except FileNotFoundError, KeyError:
                logging.error(
                    "[%s] - Credentials file not found at %s or invalid data. "
                    "The file must be a json with a 'refresh_token' field set to a valid refresh token.",
                    self.ME.upper(),
                    self.credentials_path,
                )
                return False

            logging.info("[%s] - Refreshing access token", self.ME.upper())
            url = "https://oauth.secure.pixiv.net/auth/token"
            data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "get_secure_url": "1",
            }
            async with httpx.AsyncClient(timeout=cf.asynctimeoutseconds()) as session:
                res = await session.post(url, headers=self.headers, data=data)
            if res.status_code >= 400:
                logging.debug("[%s] - res text: %s", self.ME.upper(), res.text)
                raise ConnectionRefusedError("Invalid refresh token")

            data = res.json()["response"]
            assert isinstance(data["user"], dict)
            self.username = data["user"]["name"]
            self.access_token = data["access_token"]
            self.valid_until = float(data["expires_in"]) + time.time()
            return True

        def setup_headers() -> bool:
            self.session.headers = self.headers
            return True

        default_header()
        if await get_token():
            logging.debug("[%s] - Access token gotted! %s", self.ME.upper(), self.access_token)
            if not bearer_header():
                return False

        if not setup_headers():
            return False

        return True

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        def _extract_tags() -> list[str]:
            tags = []
            if not json_data:
                raise
            if not isinstance(json_data["tags"], list):
                raise

            for tag in json_data["tags"]:
                if tag["translated_name"] and tag["translated_name"] != "None":
                    tags.append(tag["translated_name"])
                else:
                    tags.append(tag["name"])

            if json_data.get("illust_ai_type", 0) == 2:
                tags.append("AI-generated")

            return tags

        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post_id nor json_data given (one is necessary).")

            await self.LIMIT.wait()
            res = await self.session.get(f"{self.base_api_url}/v1/illust/detail", params={"illust_id": str(post_id)})
            if res.status_code != 200:
                raise cf.ExtractorExitError("Could not get post data from %s ", post_id)
            json_data = res.json()["illust"]

        post_id = str(json_data["id"])
        user_id = str(json_data["user"]["id"])

        elements: scraper.PostElement | list[scraper.PostElement]
        if json_data["meta_single_page"]:  # single image
            download_url = json_data["meta_single_page"]["original_image_url"]
            assert isinstance(download_url, str)
            extension = f.match_extension(download_url)
            if not extension:
                msg = f"[{self.ME.upper()}] - Post {post_id} gave a download url {download_url} without a valid extension ."
                logging.error(msg)
                raise cf.ExtractorSkipError(msg) from AttributeError
            elements = scraper.PostElementLinks(download_url=download_url, extension=extension)

        elif json_data["meta_pages"]:  # multiple images
            elements = []
            for image in json_data["meta_pages"]:
                download_url = image["image_urls"]["original"]
                assert isinstance(download_url, str)
                extension = f.match_extension(download_url)
                if not extension:
                    msg = f"[{self.ME.upper()}] - Post {post_id} gave a download url {download_url} without a valid extension ."
                    logging.error(msg)
                    raise cf.ExtractorSkipError(msg) from AttributeError

                elements.append(scraper.PostElementLinks(download_url=download_url, extension=extension))

        else:
            logging.error("[%s] - Could not extract post data from post %s ", self.ME.upper(), post_id)
            raise cf.ExtractorExitError("Could not extract post data from post %s ", post_id)

        result = scraper.PostData(
            identifier=post_id,
            title=json_data.get("title", "unknown title"),
            source=user_id,
            elements=elements,
            tags=scraper.TagsData(tags=_extract_tags()),
        )
        return result

    async def _endpoint_fetch_posts(
        self, endpoint: Literal["user/illusts", "search/illust"], params: dict[str, str | int], update_ids: list[str] | None = None
    ) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        offset = 0
        while True:
            await self.LIMIT.wait()
            params["offset"] = offset
            res = await self.session.get(f"{self.base_api_url}/v1/{endpoint}", params=params)

            try:
                for image in res.json()["illusts"]:
                    if str(image["id"]) in update_ids:
                        return
                    yield await self._get_post_data(json_data=image)

                if res.json()["next_url"]:
                    matched = re.search(r"offset=(.+)", res.json()["next_url"])
                    assert matched
                    offset = int(matched.group(1))
                else:
                    return

            except KeyError, AttributeError:
                await self.init()
                continue

    async def save_file(self, url: str, path: Path, filename: str) -> bool:
        # if header does not have this stuff, it doesnt work. finding this out took me 2 hours - i want to die
        h = {"Referer": "https://app-api.pixiv.net/"}
        await self.LIMIT.wait()
        return await f.download_file(config=self.config, url=url, headers=h, path=path, filename=filename)


@final
class PixivArtistAPI(PixivRoot):
    URL_TAG = "https://www.pixiv.net/en/users/{tagname}"
    TAG_PATTERN = r"(?:https?://)?(?:www\.)?pixiv\.net/(?:en/)?users/(\d+)"

    ME = "pixiv-artists"

    async def does_this_exist(self, tagname: str) -> bool:
        tagname = self.format_tagname(tagname)
        await self.LIMIT.wait()
        res = await self.session.get(f"{self.base_api_url}/v1/user/illusts", params={"user_id": tagname})
        if res.status_code == 429:
            raise cf.ExtractorStopError("Rate limited")
        return bool("user" in res.json()) and bool(str(res.json()["user"]["id"]) == tagname) and bool(res.json()["illusts"])

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        params: dict[str, str | int] = {"user_id": self.format_tagname(tagname)}
        async for entry in self._endpoint_fetch_posts("user/illusts", params, update_ids=update_ids):
            yield entry


@final
class PixivTagAPI(PixivRoot):
    URL_TAG = "https://www.pixiv.net/en/tags/{tagname}/artworks"
    TAG_PATTERN = r"(?:https?://)?(?:www\.)?pixiv\.net/(?:en/)?tags/([^/?=]+)(?:/artworks)?"

    ME = "pixiv-tags"

    async def does_this_exist(self, tagname: str) -> bool:
        await self.LIMIT.wait()
        res = await self.session.get(
            f"{self.base_api_url}/v1/search/illust", params={"word": self.format_tagname(tagname), "search_target": "partial_match_for_tags"}
        )
        if res.status_code == 429:
            raise cf.ExtractorStopError("Rate limited")
        return bool(res.json().get("illusts"))

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        params: dict[str, str | int] = {"word": self.format_tagname(tagname), "search_target": "partial_match_for_tags"}
        async for entry in self._endpoint_fetch_posts("search/illust", params, update_ids=update_ids):
            yield entry
