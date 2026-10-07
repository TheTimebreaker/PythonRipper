"""Main module for interacting with https://rule34.xxx/ ."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Mapping
from typing import Any, Literal, final

import aiofiles
import asynciolimiter
import httpx
import requests

import pythonripper.toolbox.centralfunctions as cf
import pythonripper.toolbox.files as f
import pythonripper.toolbox.scraperclasses as scraper
from pythonripper.toolbox.config.model import Rule34xxxRatings


@final
class Rule34xxxAPI(scraper.DownloadhistoryScraper):
    HOMEPAGE = "https://rule34.xxx/"
    API_URL = "https://api.rule34.xxx/index.php"
    URL_TAG = "https://rule34.xxx/index.php?page=post&s=list&tags={tagname}"

    POST_PATTERN = r"(?:https?://)?(?:www\.)?rule34\.xxx.*id=(\d+)"
    TAG_PATTERN = r"https://(?:www\.)?rule34\.xxx/index\.php\?(?:.+)?tags=([^/&\?]+)"
    FILENAME_TO_ID_PATTERN = r"rule34xxx_(\d+)_"

    ME = "rule34xxx"
    WEBSITE_NAME = ME
    LIMIT = asynciolimiter.LeakyBucketLimiter(1.8, capacity=8)
    SPACE_REPLACE = "_"
    IS_GOOGLE_SEARCHABLE = True

    session: httpx.AsyncClient

    async def init(self) -> bool:
        self.credentials_path = self.config.paths._credentials() / "rule34xxx_credentials.json"
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
                    "[%s] - The credentials file at %s either does not exist or is invalid. "
                    "API access requires a api_key and user_id in this file. "
                    "Please create an account for rule34xxx, navigate to the options, find the API credentials, "
                    "and enter the required values in the file.",
                    self.ME.upper(),
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

    async def request(self, url: str, params: Mapping[str, str | int] | None = None) -> httpx.Response:
        for i in (5, 5, 5, 7, 10, 10, 60, 60):
            await self.LIMIT.wait()
            res = await self.session.get(url, params=params)
            if res.status_code == 429:
                logging.warning("[%s] - waiting because status code is %s", self.ME.upper(), res.status_code)
                await asyncio.sleep(i)
                continue

            return res
        raise cf.ExtractorStopError("Probably hit a hard rate limit")

    async def does_this_exist(self, tagname: str) -> bool:
        params: dict[str, str | int] = {"s": "post", "tags": self.format_tagname(tagname)}
        res = await self.request(self.API_URL, params=params)
        return bool(res.text)

    def is_content_rating_allowed(self, data: scraper.PostData) -> bool:
        allowed_ratings = self.config.settings.extractor.rule34xxx.allowed_ratings
        return data["rating"] in allowed_ratings

    def create_ratings_searchtag(self, formatted_tagname: str) -> str:
        cfg = self.config.settings.extractor.rule34xxx.allowed_ratings
        len_cfg = len(cfg)
        if len(set(Rule34xxxRatings)) != 3:
            raise NotImplementedError("RULE34XXX - Ratings set length is not 3!")

        if len_cfg == 0:
            msg = f"[{self.ME.upper()}] - Can't fetch posts, when none of the content ratings are enabled. Configure this in your settings!"
            logging.error(msg)
            raise cf.ExtractorStopError(msg)

        elif len_cfg == 1:
            return f"{formatted_tagname} rating:{next(iter(cfg))}"

        elif len_cfg == 2:  # We invert the set at 3 because less words in the search tag == lower risk of being timed out
            inverted_cfg = set(Rule34xxxRatings) - cfg
            return f"{formatted_tagname} -rating:{next(iter(inverted_cfg))}"

        elif len_cfg == 3:
            return formatted_tagname

        else:
            raise NotImplementedError

    async def _get_post_data(self, post_id: str | None = None, json_data: dict[str, Any] | None = None) -> scraper.PostData:
        if json_data is None:
            if post_id is None:
                raise ValueError("Neither post_id nor json_data given (one is necessary).")

            params = {"s": "post", "id": post_id}
            res = await self.request(self.API_URL, params=params)
            try:
                json_data = res.json()[0]
            except json.JSONDecodeError as error:
                raise cf.ExtractorSkipError from error

        rating_field: str | Literal[False] = json_data.get("rating", False)
        if not rating_field:
            logging.error("[%s] - No rating field found in json data from post %s", self.ME.upper(), post_id)
            raise cf.ExtractorSkipError("No rating field found") from KeyError
        rating_field = rating_field.lower()
        #fmt:off
        rating:str|Literal[False] = (
            Rule34xxxRatings.SAFE if rating_field == "safe" else
            Rule34xxxRatings.QUESTIONABLE if rating_field == "questionable" else
            Rule34xxxRatings.EXPLICIT if rating_field == "explicit" else False
        )
        #fmt:on
        if not rating:
            logging.error("[%s] - Rating could not be extracted from json data from post %s", self.ME.upper(), post_id)
            raise cf.ExtractorSkipError from KeyError

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
                tags=[self.invert_formatting(tag) for tag in str(json_data["tags"]).split(" ")],
            ),
            rating=rating,
        )

    async def _fetch_posts(
        self, tagname: str, update_ids: list[str] | None = None, ignore_contentfilters: bool = False
    ) -> AsyncGenerator[scraper.PostData]:
        if update_ids is None:
            update_ids = []

        tagname = self.format_tagname(tagname)
        if ignore_contentfilters is False:
            tagname = self.create_ratings_searchtag(tagname)

        more_files = True
        params: dict[str, str | int] = {"s": "post", "limit": 100, "pid": 0, "tags": tagname}
        assert isinstance(params["pid"], int)
        data: dict[Any, Any] = {}

        while more_files:
            res = await self.request(self.API_URL, params=params)

            # API limit reached. Recalculation of tagNameFormatted
            if params["pid"] > 2000:
                last2000id = ...  # data[-1]["id"]
                params["pid"] = 0
                params["tags"] = f"{tagname} id:<{last2000id}"
                continue

            try:
                # Empty json <=> no more files there
                if res.status_code == 200 and not res.json():
                    return
            except requests.exceptions.JSONDecodeError, json.decoder.JSONDecodeError:
                logging.error("[%s] Could not fully download tag %s due to empty response. Maybe the tag has been removed?", self.ME.upper(), tagname)
                return

            data = res.json()
            for post in data:
                post_data = await self._get_post_data(json_data=post)
                if str(post_data["identifier"]) in update_ids:
                    return
                yield post_data

            more_files = bool(data)
            params["pid"] += 1
