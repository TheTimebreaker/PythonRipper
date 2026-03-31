"""Main module for interacting with https://gelbooru.com/ ."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, final

import aiofiles
import asynciolimiter
import httpx

import toolbox.centralfunctions as cf
import toolbox.files as f
import toolbox.scraperclasses as scraper


@final
class GelbooruAPI(scraper.BooruScraper):
    API_URL = "https://gelbooru.com/index.php"
    POST_URL = "https://gelbooru.com/index.php?page=post&s=view&id={post_id}"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?gelbooru\.com.*id=(\d+)"

    ME = "gelbooru"
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.random_tag_name = "sort:random"
        self.credentials_path = self.config._credentials_path() / "gelbooru_credentials.json"
        self.download_headers = {"Referer": self.API_URL}
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds())

        async def read_credentials() -> bool:
            try:
                async with aiofiles.open(self.credentials_path) as file:
                    data = json.loads(await file.read())
                self.api_key = data["api_key"]
                self.user_id = data["user_id"]
                return True
            except FileExistsError, KeyError:
                logging.error(
                    "[GELBOORU] - The credentials file at %s either does not exist or is invalid. "
                    "API access requires a api_key and user_id in this file. "
                    "Please create an account for Gelbooru, navigate to the options, find the API credentials, "
                    "and enter the required values in the file.",
                    self.credentials_path,
                )
                return False

        def setup_session() -> bool:
            params = {
                "q": "index",
                "page": "dapi",
                "json": "1",
                "api_key": self.api_key,
                "user_id": self.user_id,
            }
            self.session.params = params
            self.session.headers = self.headers
            return True

        async def test_session() -> bool:
            params: dict[str, str | int] = {"s": "post", "limit": 1}
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)
            validity = res.status_code == 200
            if not validity:
                logging.error("[GELBOORU] - Created session could not be verified to work. Maybe your API credentials aren't valid?")
            return validity

        if not await read_credentials():
            return False

        if not setup_session():
            return False

        if not await test_session():
            return False

        return True

    async def does_this_exist(self, tagname: str) -> bool:
        params: dict[str, str | int] = {"s": "post", "tags": self.format_tagname(tagname)}
        await self.LIMIT.wait()
        res = await self.session.get(self.API_URL, params=params)
        return "post" in res.json() and bool(res.json()["post"])

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post id nor json_data given (one is necessary).")
            params = {"s": "post", "id": post_id}
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)
            json_data = res.json()["post"][0]
        if post_id is None:
            post_id = str(json_data["id"])

        tags = scraper.TagsData(
            tags=[tag.replace(self.SPACE_REPLACE, " ") for tag in str(json_data["tags"]).split(" ")],
        )

        download_url = json_data["file_url"]
        extension = f.match_extension(download_url)
        assert extension
        return scraper.PostData(
            identifier=post_id,
            filehash=str(json_data["md5"]),
            elements=scraper.PostElementLinks(download_url=download_url, extension=extension),
            tags=tags,
        )

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        more_files = True
        truepage = 0
        data: list[dict[str, str | int]] = []
        tagname = self.format_tagname(tagname)

        params: dict[str, str | int] = {"s": "post", "limit": 100, "pid": 0, "tags": tagname}
        assert isinstance(params["pid"], int)
        while more_files:
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)

            # API limit reached. Recalculation of tagNameFormatted
            if res.text == "Too deep! Pull it back some. Holy fuck.":
                params["pid"] = 0
                params["tags"] = f"{tagname}+id:<{data[-1]["id"]}"
                continue

            # no posts found?
            if res.status_code == 401:
                logging.error("[GELBOORU] - Tag %s returned 401 html response. Removed?", tagname)
                raise cf.ExtractorExitError("Tag %s returned 401 html response. Removed?", tagname)

            # Paginated past last post(s)
            if res.status_code == 200 and "post" not in res.json().keys():
                return

            # The part that actually yields you data
            data = res.json()["post"]
            for post in data:
                if str(post["id"]) in update_ids:
                    return
                yield await self._get_post_data(json_data=post)

            more_files = bool(data)
            params["pid"] += 1
            truepage += 1
