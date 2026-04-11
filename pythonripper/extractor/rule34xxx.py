"""Main module for interacting with https://rule34.xxx/ ."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, final

import aiofiles
import asynciolimiter
import httpx
import requests

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper


@final
class Rule34xxxAPI(scraper.BooruScraper):
    HOMEPAGE = "https://rule34.xxx/"
    API_URL = "https://api.rule34.xxx/index.php"
    URL_TAG = "https://rule34.xxx/index.php?page=post&s=list&tags={tagname}"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?rule34\.xxx.*id=(\d+)"
    TAG_PATTERN = r"https://(?:www\.)?rule34\.xxx/index\.php\?(?:.+)?tags=([^/&\?]+)"

    ME = "rule34xxx"
    LIMIT = asynciolimiter.Limiter(100)
    SPACE_REPLACE = "_"
    IS_GOOGLE_SEARCHABLE = True

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.credentials_path = self.config._credentials_path() / "rule34xxx_credentials.json"
        self.api_key: str
        self.user_id: str
        self.session = httpx.AsyncClient(timeout=cf.asynctimeoutseconds(), headers=self.headers)

        async def read_credentials() -> bool:
            try:
                async with aiofiles.open(self.credentials_path) as file:
                    data = json.loads(await file.read())
                self.api_key = data["api_key"]
                self.user_id = data["user_id"]
                return True
            except FileExistsError, KeyError:
                logging.error(
                    "[RULE34XXX] - The credentials file at %s either does not exist or is invalid. "
                    "API access requires a api_key and user_id in this file. "
                    "Please create an account for rule34xxx, navigate to the options, find the API credentials, "
                    "and enter the required values in the file.",
                    self.credentials_path,
                )
                return False

        def setup_session() -> bool:
            params: dict[str, str | int] = {"q": "index", "page": "dapi", "json": 1, "api_key": self.api_key, "user_id": self.user_id}
            self.session.params = params
            return True

        if not await read_credentials():
            return False

        if not setup_session():
            return False

        return True

    async def does_this_exist(self, tagname: str) -> bool:
        params: dict[str, str | int] = {"s": "post", "tags": self.format_tagname(tagname)}
        await self.LIMIT.wait()
        res = await self.session.get(self.API_URL, params=params)
        return bool(res.text)

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post_id nor json_data given (one is necessary).")

            params = {"s": "post", "id": post_id}
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)
            json_data = res.json()[0]

        download_url = json_data["file_url"]
        assert isinstance(download_url, str)
        extension = f.match_extension(download_url)
        if not extension:
            msg = f"[{self.ME.upper()}] - Post {post_id} gave a download url {download_url} without a valid extension ."
            logging.error(msg)
            raise cf.ExtractorSkipError(msg) from AttributeError
        return scraper.PostData(
            identifier=json_data["id"],
            filehash=json_data["hash"],
            elements=scraper.PostElementLinks(download_url=download_url, extension=extension),
            tags=scraper.TagsData(
                tags=[tag.replace(self.SPACE_REPLACE, " ") for tag in str(json_data["tags"]).split(" ")],
            ),
        )

    async def _fetch_posts(self, tagname: str, update_ids: list[str] | None = None) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)

        more_files = True
        params: dict[str, str | int] = {"s": "post", "limit": 100, "pid": 0, "tags": tagname}
        assert isinstance(params["pid"], int)
        data: dict[Any, Any] = {}

        while more_files:
            await self.LIMIT.wait()
            res = await self.session.get(self.API_URL, params=params)

            # API limit reached. Recalculation of tagNameFormatted
            if params["pid"] > 2000:
                last2000id = ...  # data[-1]["id"]
                params["pid"] = 0
                params["tags"] = f"{tagname}+id:<{last2000id}"
                continue

            try:
                # Empty json <=> no more files there
                if res.status_code == 200 and not res.json():
                    return
            except requests.exceptions.JSONDecodeError, json.decoder.JSONDecodeError:
                logging.error("[RULE34XXX] Could not fully download tag %s due to empty response. Maybe the tag has been removed?", tagname)
                return

            data = res.json()
            for post in data:
                post_data = await self._get_post_data(json_data=post)
                if post_data["identifier"] in update_ids:
                    return
                yield post_data

            more_files = bool(data)
            params["pid"] += 1
